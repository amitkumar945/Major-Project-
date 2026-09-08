/**
 * Minimal QR Code encoder (ISO/IEC 18004), byte mode.
 *
 * Vendored deliberately rather than pulled from a CDN: the QR page must render
 * on a lecture-hall projector or a print preview with no network, the service
 * worker caches our own assets only, and a poster that silently fails to draw
 * because a CDN is blocked is worse than useless.
 *
 * Scope is exactly what this project needs and no more: byte mode, versions
 * 1-10, all four error-correction levels, full mask evaluation. That covers
 * URLs up to ~270 characters, far beyond any address we print.
 *
 * Exposes `window.QRCodeGen.generate(text, ecLevel) -> { size, modules }`
 * where `modules[row][col]` is a boolean (true = dark).
 */
(function () {
  'use strict';

  // --------------------------------------------------------------- GF(256)
  // Reed-Solomon arithmetic over the field the QR spec fixes (primitive
  // polynomial 0x11D). Log/antilog tables make multiplication a lookup.

  var EXP = new Uint8Array(512);
  var LOG = new Uint8Array(256);

  (function buildTables() {
    var x = 1;
    for (var i = 0; i < 255; i++) {
      EXP[i] = x;
      LOG[x] = i;
      x <<= 1;
      if (x & 0x100) x ^= 0x11d;
    }
    for (var j = 255; j < 512; j++) EXP[j] = EXP[j - 255];
  })();

  function gfMul(a, b) {
    if (a === 0 || b === 0) return 0;
    return EXP[LOG[a] + LOG[b]];
  }

  /** Generator polynomial for `degree` error-correction codewords. */
  function rsGenerator(degree) {
    var poly = [1];
    for (var d = 0; d < degree; d++) {
      var next = new Array(poly.length + 1).fill(0);
      for (var i = 0; i < poly.length; i++) {
        next[i] ^= poly[i];
        next[i + 1] ^= gfMul(poly[i], EXP[d]);
      }
      poly = next;
    }
    return poly;
  }

  /** The `degree` EC codewords for one data block. */
  function rsEncode(data, degree) {
    var gen = rsGenerator(degree);
    var rem = new Array(degree).fill(0);
    for (var i = 0; i < data.length; i++) {
      var factor = data[i] ^ rem[0];
      rem.shift();
      rem.push(0);
      for (var j = 0; j < degree; j++) rem[j] ^= gfMul(gen[j + 1], factor);
    }
    return rem;
  }

  // ------------------------------------------------------------- spec data
  // Per version: total codewords, then for each EC level the EC codewords per
  // block and the block counts (group 1, group 2). Straight from the tables in
  // ISO/IEC 18004 Annex D. Versions 1-10 only.

  var EC_LEVELS = { L: 0, M: 1, Q: 2, H: 3 };

  // [ecCodewordsPerBlock, numBlocksGroup1, numBlocksGroup2] indexed [version][level]
  var EC_TABLE = {
    1:  [[7, 1, 0], [10, 1, 0], [13, 1, 0], [17, 1, 0]],
    2:  [[10, 1, 0], [16, 1, 0], [22, 1, 0], [28, 1, 0]],
    3:  [[15, 1, 0], [26, 1, 0], [18, 2, 0], [22, 2, 0]],
    4:  [[20, 1, 0], [18, 2, 0], [26, 2, 0], [16, 4, 0]],
    5:  [[26, 1, 0], [24, 2, 0], [18, 2, 2], [22, 2, 2]],
    6:  [[18, 2, 0], [16, 4, 0], [24, 4, 0], [28, 4, 0]],
    7:  [[20, 2, 0], [18, 4, 0], [18, 2, 4], [26, 4, 1]],
    8:  [[24, 2, 0], [22, 2, 2], [22, 4, 2], [26, 4, 2]],
    9:  [[30, 2, 0], [22, 3, 2], [20, 4, 4], [24, 4, 4]],
    10: [[18, 2, 2], [26, 4, 1], [24, 6, 2], [28, 6, 2]],
  };

  /** Total codewords (data + EC) for versions 1-10. */
  var TOTAL_CODEWORDS = {
    1: 26, 2: 44, 3: 70, 4: 100, 5: 134,
    6: 172, 7: 196, 8: 242, 9: 292, 10: 346,
  };

  /** Alignment-pattern centre coordinates for versions 1-10. */
  var ALIGNMENT = {
    1: [], 2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30],
    6: [6, 34], 7: [6, 22, 38], 8: [6, 24, 42], 9: [6, 26, 46], 10: [6, 28, 50],
  };

  function totalDataCodewords(version, level) {
    var spec = EC_TABLE[version][level];
    var blocks = spec[1] + spec[2];
    return TOTAL_CODEWORDS[version] - spec[0] * blocks;
  }

  // ------------------------------------------------------------- bit buffer

  function BitBuffer() {
    this.bits = [];
  }
  BitBuffer.prototype.put = function (value, length) {
    for (var i = length - 1; i >= 0; i--) this.bits.push((value >>> i) & 1);
  };
  BitBuffer.prototype.length = function () {
    return this.bits.length;
  };

  // ---------------------------------------------------------------- encode

  function toUtf8Bytes(text) {
    var out = [];
    var encoded = encodeURIComponent(text);
    for (var i = 0; i < encoded.length; i++) {
      if (encoded[i] === '%') {
        out.push(parseInt(encoded.substr(i + 1, 2), 16));
        i += 2;
      } else {
        out.push(encoded.charCodeAt(i));
      }
    }
    return out;
  }

  /** Smallest version that fits `byteLength` bytes at this EC level. */
  function chooseVersion(byteLength, level) {
    for (var v = 1; v <= 10; v++) {
      var capacityBits = totalDataCodewords(v, level) * 8;
      var countBits = v < 10 ? 8 : 16;
      // 4 mode bits + character count + the data itself.
      if (4 + countBits + byteLength * 8 <= capacityBits) return v;
    }
    throw new Error('Text too long for a version-10 QR code (' + byteLength + ' bytes).');
  }

  function buildCodewords(bytes, version, level) {
    var dataCount = totalDataCodewords(version, level);
    var buffer = new BitBuffer();

    buffer.put(0b0100, 4);                          // byte mode
    buffer.put(bytes.length, version < 10 ? 8 : 16); // character count
    for (var i = 0; i < bytes.length; i++) buffer.put(bytes[i], 8);

    // Terminator, up to four zero bits.
    var capacity = dataCount * 8;
    var terminator = Math.min(4, capacity - buffer.length());
    buffer.put(0, terminator);

    // Pad to a byte boundary, then alternate the two spec pad bytes.
    while (buffer.length() % 8 !== 0) buffer.bits.push(0);

    var codewords = [];
    for (var b = 0; b < buffer.bits.length; b += 8) {
      var byte = 0;
      for (var k = 0; k < 8; k++) byte = (byte << 1) | buffer.bits[b + k];
      codewords.push(byte);
    }
    var pads = [0xec, 0x11];
    var p = 0;
    while (codewords.length < dataCount) codewords.push(pads[p++ % 2]);

    return codewords;
  }

  /**
   * Split into blocks, compute EC per block, then interleave both as the spec
   * requires. Interleaving is what lets a scanner recover from a smudge that
   * wipes out a contiguous run of modules.
   */
  function interleave(codewords, version, level) {
    var spec = EC_TABLE[version][level];
    var ecPerBlock = spec[0];
    var blocks1 = spec[1];
    var blocks2 = spec[2];
    var totalBlocks = blocks1 + blocks2;

    var shortLen = Math.floor(codewords.length / totalBlocks);
    var dataBlocks = [];
    var ecBlocks = [];
    var offset = 0;

    for (var i = 0; i < totalBlocks; i++) {
      var len = i < blocks1 ? shortLen : shortLen + 1;
      var block = codewords.slice(offset, offset + len);
      offset += len;
      dataBlocks.push(block);
      ecBlocks.push(rsEncode(block, ecPerBlock));
    }

    var result = [];
    var maxData = shortLen + (blocks2 > 0 ? 1 : 0);
    for (var c = 0; c < maxData; c++) {
      for (var b = 0; b < totalBlocks; b++) {
        if (c < dataBlocks[b].length) result.push(dataBlocks[b][c]);
      }
    }
    for (var e = 0; e < ecPerBlock; e++) {
      for (var bb = 0; bb < totalBlocks; bb++) result.push(ecBlocks[bb][e]);
    }
    return result;
  }

  // ---------------------------------------------------------------- matrix

  function createMatrix(size) {
    var modules = [];
    var reserved = [];
    for (var r = 0; r < size; r++) {
      modules.push(new Array(size).fill(false));
      reserved.push(new Array(size).fill(false));
    }
    return { modules: modules, reserved: reserved, size: size };
  }

  function placeFinder(m, row, col) {
    for (var r = -1; r <= 7; r++) {
      for (var c = -1; c <= 7; c++) {
        var rr = row + r;
        var cc = col + c;
        if (rr < 0 || rr >= m.size || cc < 0 || cc >= m.size) continue;
        var dark =
          (r >= 0 && r <= 6 && (c === 0 || c === 6)) ||
          (c >= 0 && c <= 6 && (r === 0 || r === 6)) ||
          (r >= 2 && r <= 4 && c >= 2 && c <= 4);
        m.modules[rr][cc] = dark;
        m.reserved[rr][cc] = true;
      }
    }
  }

  function placeAlignment(m, version) {
    var centres = ALIGNMENT[version];
    for (var i = 0; i < centres.length; i++) {
      for (var j = 0; j < centres.length; j++) {
        var row = centres[i];
        var col = centres[j];
        // Skip the three corners already occupied by finder patterns.
        if (m.reserved[row][col]) continue;
        for (var r = -2; r <= 2; r++) {
          for (var c = -2; c <= 2; c++) {
            var dark = Math.max(Math.abs(r), Math.abs(c)) !== 1;
            m.modules[row + r][col + c] = dark;
            m.reserved[row + r][col + c] = true;
          }
        }
      }
    }
  }

  function placeTiming(m) {
    for (var i = 8; i < m.size - 8; i++) {
      var dark = i % 2 === 0;
      if (!m.reserved[6][i]) { m.modules[6][i] = dark; m.reserved[6][i] = true; }
      if (!m.reserved[i][6]) { m.modules[i][6] = dark; m.reserved[i][6] = true; }
    }
  }

  function reserveFormat(m) {
    for (var i = 0; i < 9; i++) {
      if (!m.reserved[8][i]) { m.reserved[8][i] = true; m.modules[8][i] = false; }
      if (!m.reserved[i][8]) { m.reserved[i][8] = true; m.modules[i][8] = false; }
    }
    for (var j = 0; j < 8; j++) {
      m.reserved[8][m.size - 1 - j] = true;
      m.reserved[m.size - 1 - j][8] = true;
    }
    // The always-dark module beside the lower-left finder.
    m.modules[m.size - 8][8] = true;
    m.reserved[m.size - 8][8] = true;
  }

  /** Zig-zag data placement, right to left, skipping the timing column. */
  function placeData(m, data) {
    var bitIndex = 0;
    var upward = true;

    for (var right = m.size - 1; right >= 1; right -= 2) {
      if (right === 6) right = 5; // column 6 is the vertical timing pattern
      for (var step = 0; step < m.size; step++) {
        var row = upward ? m.size - 1 - step : step;
        for (var c = 0; c < 2; c++) {
          var col = right - c;
          if (m.reserved[row][col]) continue;
          var bit = false;
          if (bitIndex < data.length * 8) {
            bit = ((data[bitIndex >>> 3] >>> (7 - (bitIndex & 7))) & 1) === 1;
          }
          m.modules[row][col] = bit;
          bitIndex++;
        }
      }
      upward = !upward;
    }
  }

  var MASKS = [
    function (r, c) { return (r + c) % 2 === 0; },
    function (r) { return r % 2 === 0; },
    function (r, c) { return c % 3 === 0; },
    function (r, c) { return (r + c) % 3 === 0; },
    function (r, c) { return (Math.floor(r / 2) + Math.floor(c / 3)) % 2 === 0; },
    function (r, c) { return ((r * c) % 2) + ((r * c) % 3) === 0; },
    function (r, c) { return (((r * c) % 2) + ((r * c) % 3)) % 2 === 0; },
    function (r, c) { return (((r + c) % 2) + ((r * c) % 3)) % 2 === 0; },
  ];

  function applyMask(m, maskIndex) {
    var fn = MASKS[maskIndex];
    var out = createMatrix(m.size);
    for (var r = 0; r < m.size; r++) {
      for (var c = 0; c < m.size; c++) {
        out.modules[r][c] = m.reserved[r][c]
          ? m.modules[r][c]
          : m.modules[r][c] !== fn(r, c);
        out.reserved[r][c] = m.reserved[r][c];
      }
    }
    return out;
  }

  /** BCH(15,5) format information, masked with the spec's 0x5412. */
  function formatBits(level, maskIndex) {
    var LEVEL_BITS = { 0: 0b01, 1: 0b00, 2: 0b11, 3: 0b10 }; // L,M,Q,H
    var data = (LEVEL_BITS[level] << 3) | maskIndex;
    var value = data << 10;
    for (var i = 4; i >= 0; i--) {
      if ((value >>> (10 + i)) & 1) value ^= 0b10100110111 << i;
    }
    return ((data << 10) | value) ^ 0b101010000010010;
  }

  function placeFormat(m, level, maskIndex) {
    var bits = formatBits(level, maskIndex);

    // The 15 format bits are written most-significant first. `i` counts from
    // the MSB, so bit (14 - i) is the one this position carries - reading the
    // word the other way round produces a matrix that still looks like a QR
    // code but that no scanner can decode.
    for (var i = 0; i < 15; i++) {
      var bit = ((bits >>> (14 - i)) & 1) === 1;

      // Copy 1, around the top-left finder: down the left column, then left
      // along the top row, skipping the timing module at index 6.
      if (i < 6) m.modules[i][8] = bit;
      else if (i === 6) m.modules[7][8] = bit;
      else if (i === 7) m.modules[8][8] = bit;
      else if (i === 8) m.modules[8][7] = bit;
      else m.modules[8][14 - i] = bit;

      // Copy 2, split between the other two finders so the format survives
      // damage to any one corner.
      if (i < 8) m.modules[8][m.size - 1 - i] = bit;
      else m.modules[m.size - 15 + i][8] = bit;
    }
  }

  // ------------------------------------------------------ mask penalty rules

  function penalty(m) {
    var size = m.size;
    var score = 0;
    var r, c, run, i;

    // Rule 1: runs of five or more same-coloured modules in a line.
    for (r = 0; r < size; r++) {
      run = 1;
      for (c = 1; c < size; c++) {
        if (m.modules[r][c] === m.modules[r][c - 1]) {
          run++;
        } else {
          if (run >= 5) score += 3 + (run - 5);
          run = 1;
        }
      }
      if (run >= 5) score += 3 + (run - 5);
    }
    for (c = 0; c < size; c++) {
      run = 1;
      for (r = 1; r < size; r++) {
        if (m.modules[r][c] === m.modules[r - 1][c]) {
          run++;
        } else {
          if (run >= 5) score += 3 + (run - 5);
          run = 1;
        }
      }
      if (run >= 5) score += 3 + (run - 5);
    }

    // Rule 2: 2x2 blocks of one colour.
    for (r = 0; r < size - 1; r++) {
      for (c = 0; c < size - 1; c++) {
        var v = m.modules[r][c];
        if (v === m.modules[r][c + 1] && v === m.modules[r + 1][c] && v === m.modules[r + 1][c + 1]) {
          score += 3;
        }
      }
    }

    // Rule 3: finder-like 1:1:3:1:1 patterns, which confuse a scanner.
    var P1 = [true, false, true, true, true, false, true, false, false, false, false];
    var P2 = [false, false, false, false, true, false, true, true, true, false, true];
    function matches(get, start) {
      var a = true, b = true;
      for (var k = 0; k < 11; k++) {
        var val = get(start + k);
        if (val !== P1[k]) a = false;
        if (val !== P2[k]) b = false;
      }
      return a || b;
    }
    for (r = 0; r < size; r++) {
      for (c = 0; c + 11 <= size; c++) {
        if (matches(function (x) { return m.modules[r][x]; }, c)) score += 40;
      }
    }
    for (c = 0; c < size; c++) {
      for (r = 0; r + 11 <= size; r++) {
        if (matches(function (x) { return m.modules[x][c]; }, r)) score += 40;
      }
    }

    // Rule 4: deviation from a 50/50 dark ratio.
    var dark = 0;
    for (r = 0; r < size; r++) {
      for (c = 0; c < size; c++) if (m.modules[r][c]) dark++;
    }
    var percent = (dark * 100) / (size * size);
    score += Math.floor(Math.abs(percent - 50) / 5) * 10;

    return score;
  }

  // ----------------------------------------------------------------- public

  /**
   * Encode `text` as a QR matrix.
   * @param {string} text
   * @param {string} ecLevel 'L' | 'M' | 'Q' | 'H' (default 'M')
   * @returns {{size:number, modules:boolean[][], version:number}}
   */
  function generate(text, ecLevel) {
    var level = EC_LEVELS[(ecLevel || 'M').toUpperCase()];
    if (level === undefined) throw new Error('Unknown EC level: ' + ecLevel);

    var bytes = toUtf8Bytes(String(text));
    var version = chooseVersion(bytes.length, level);
    var size = version * 4 + 17;

    var codewords = buildCodewords(bytes, version, level);
    var finalData = interleave(codewords, version, level);

    var base = createMatrix(size);
    placeFinder(base, 0, 0);
    placeFinder(base, 0, size - 7);
    placeFinder(base, size - 7, 0);
    placeAlignment(base, version);
    placeTiming(base);
    reserveFormat(base);
    placeData(base, finalData);

    // Try every mask and keep the one the spec's penalty rules like best.
    var best = null;
    var bestScore = Infinity;
    for (var maskIndex = 0; maskIndex < 8; maskIndex++) {
      var candidate = applyMask(base, maskIndex);
      placeFormat(candidate, level, maskIndex);
      var score = penalty(candidate);
      if (score < bestScore) {
        bestScore = score;
        best = candidate;
      }
    }

    return { size: size, modules: best.modules, version: version };
  }

  /**
   * Render a matrix as a standalone SVG string.
   * Vector, so it stays razor-sharp at any print size.
   *
   * `quietZone` is in modules; the spec requires at least 4, and phone cameras
   * genuinely need that white margin to lock on.
   */
  function toSvg(result, options) {
    var opts = options || {};
    var quiet = opts.quietZone === undefined ? 4 : opts.quietZone;
    var dark = opts.dark || '#000000';
    var light = opts.light || '#ffffff';
    var total = result.size + quiet * 2;

    var path = [];
    for (var r = 0; r < result.size; r++) {
      for (var c = 0; c < result.size; c++) {
        if (result.modules[r][c]) {
          path.push('M' + (c + quiet) + ' ' + (r + quiet) + 'h1v1h-1z');
        }
      }
    }

    return (
      '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ' + total + ' ' + total + '" ' +
      'shape-rendering="crispEdges" role="img">' +
      '<rect width="' + total + '" height="' + total + '" fill="' + light + '"/>' +
      '<path d="' + path.join('') + '" fill="' + dark + '"/>' +
      '</svg>'
    );
  }

  window.QRCodeGen = { generate: generate, toSvg: toSvg };
})()
