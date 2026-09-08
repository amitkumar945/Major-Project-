/**
 * Mobile app download page.
 *
 * Renders the QR code, wires the two buttons, and adapts the page to what the
 * visitor is actually holding. It reads the public address from
 * `window.APP_CONFIG` (assets/js/appConfig.js) and the APK location from
 * `window.APP_DOWNLOAD` (below the config block in app.html), so nothing about
 * a deployment is written down twice.
 *
 * Plain non-module script, like pwa.js: this page must keep working even if
 * the app's ES modules fail to load.
 */
(function () {
  'use strict';

  var config = window.APP_CONFIG || {};
  var download = window.APP_DOWNLOAD || {};

  // The URL the QR code points at: this very page, on the public origin.
  var pageUrl = config.url ? config.url('/app.html') : location.href;

  // ------------------------------------------------------------- QR code

  function renderQr() {
    var host = document.getElementById('qr-code');
    var caption = document.getElementById('qr-url');
    if (!host) return;

    // Refuse to print a poster for an address no phone off this machine can
    // reach. A QR code holding `localhost` looks perfectly valid and fails
    // silently in the user's hand, which is the worst outcome available.
    if (!config.isPublic) {
      host.innerHTML = '';
      host.classList.add('qr--unavailable');
      host.innerHTML =
        '<p class="qr__warning"><strong>QR code not available here.</strong><br>' +
        'This page is being served from <code>' + escapeHtml(location.origin) + '</code>, ' +
        'which only works on this machine. Open the deployed site to get a ' +
        'scannable code.</p>';
      if (caption) caption.textContent = location.origin + '/app.html';
      return;
    }

    if (!window.QRCodeGen) return;

    try {
      var result = window.QRCodeGen.generate(pageUrl, 'M');
      host.innerHTML = window.QRCodeGen.toSvg(result, {
        quietZone: 2,
        dark: '#1e1b4b',
        light: '#ffffff',
      });
    } catch (error) {
      host.innerHTML = '<p class="qr__warning">Could not draw the QR code.</p>';
    }

    if (caption) caption.textContent = pageUrl;
  }

  function escapeHtml(text) {
    var div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  // ------------------------------------------------------ APK download

  function setupApk() {
    var button = document.getElementById('apk-download');
    var note = document.getElementById('apk-note');
    if (!button) return;

    // No release published yet: say so plainly rather than handing out a
    // link that 404s. The PWA route above still works, so the page is useful.
    if (!download.apkUrl) {
      button.classList.add('is-disabled');
      button.setAttribute('aria-disabled', 'true');
      button.removeAttribute('href');
      button.addEventListener('click', function (event) {
        event.preventDefault();
      });
      if (note) {
        note.textContent =
          'The Android APK has not been published yet. Use "Install app" above ' +
          '\u2014 it gives you the same system on your home screen.';
      }
      return;
    }

    button.href = download.apkUrl;
    if (note && download.apkSize) {
      note.textContent =
        'Android ' + (download.minAndroid || '6.0') + ' or newer \u00b7 ' +
        download.apkSize + (download.version ? ' \u00b7 v' + download.version : '');
    }
  }

  // -------------------------------------------------- PWA install button

  // pwa.js owns the `beforeinstallprompt` event and floats its own button.
  // This page has a proper button of its own, so it takes the event over and
  // suppresses the floating one while the visitor is here.
  var deferredPrompt = null;

  function setupInstall() {
    var button = document.getElementById('install-app');
    var note = document.getElementById('install-note');
    if (!button) return;

    var standalone = window.dsvvPwa && window.dsvvPwa.isStandalone();

    if (standalone) {
      button.classList.add('is-disabled');
      button.setAttribute('aria-disabled', 'true');
      if (note) note.textContent = 'Already installed \u2014 you are using the app right now.';
      return;
    }

    button.addEventListener('click', function () {
      if (!deferredPrompt) {
        // Either the browser has not offered installation yet, or this is a
        // browser that never fires the event (iOS Safari, Firefox). Show the
        // manual route instead of leaving a dead button.
        showManualInstructions();
        return;
      }
      deferredPrompt.prompt();
      deferredPrompt.userChoice.then(function (choice) {
        deferredPrompt = null;
        if (choice && choice.outcome === 'accepted') {
          button.classList.add('is-disabled');
          if (note) note.textContent = 'Installing\u2026 check your home screen.';
        }
      });
    });

    window.addEventListener('beforeinstallprompt', function (event) {
      event.preventDefault();
      deferredPrompt = event;
      button.classList.remove('is-muted');
      if (note) note.textContent = 'Adds the app to your home screen. No Play Store needed.';
    });

    window.addEventListener('appinstalled', function () {
      deferredPrompt = null;
      button.classList.add('is-disabled');
      if (note) note.textContent = 'Installed. Open it from your home screen.';
    });
  }

  function showManualInstructions() {
    var box = document.getElementById('manual-install');
    if (!box) return;
    box.hidden = false;
    box.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  // ------------------------------------------------------- device hints

  /** Reorders the two cards so the relevant one leads on the device in hand. */
  function applyDeviceHints() {
    var ua = navigator.userAgent || '';
    var isAndroid = /Android/i.test(ua);
    var isIos = /iPad|iPhone|iPod/i.test(ua) ||
      (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);

    var apkCard = document.getElementById('card-apk');

    // The APK is an Android binary. On a desktop it is still worth showing
    // (people download it to sideload later), but on iOS it is pure noise.
    if (isIos && apkCard) {
      apkCard.hidden = true;
      var iosNote = document.getElementById('ios-note');
      if (iosNote) iosNote.hidden = false;
    }

    if (isAndroid) {
      document.body.classList.add('is-android');
    }
  }

  // --------------------------------------------------------------- boot

  function init() {
    renderQr();
    setupApk();
    setupInstall();
    applyDeviceHints();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
