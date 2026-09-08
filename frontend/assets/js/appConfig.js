/**
 * Public app configuration.
 *
 * ONE place where the deployed address of this app is written down. The QR
 * code, the printable poster and the landing page all read it from here, so a
 * new deployment means editing a single line rather than hunting for URLs.
 *
 * This file is public and is served to every visitor. It holds only the
 * public web address - never a token, key, credential or database detail.
 * (See `docs/QR_AND_INSTALL.md`.)
 */
(function () {
  'use strict';

  /**
   * The canonical public HTTPS origin of the deployed app, with no trailing
   * slash. Example: 'https://dsvv-grievance.vercel.app'
   *
   * Leave it as an empty string to fall back to the origin the page is
   * actually being served from. That fallback is correct in production - the
   * app is served from its own domain - and it is what keeps a development
   * machine from ever baking `localhost` into a printed QR code: the QR page
   * refuses to render a poster for a non-public origin and says so instead.
   */
  var PRODUCTION_ORIGIN = '';

  /** True for origins that must never end up inside a printed QR code. */
  function isLocalOrigin(origin) {
    return /^https?:\/\/(localhost|127\.0\.0\.1|0\.0\.0\.0|\[::1\]|10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.)/i
      .test(origin || '');
  }

  var configured = (PRODUCTION_ORIGIN || '').replace(/\/+$/, '');
  var current = window.location.origin;

  window.APP_CONFIG = {
    /** The origin an explicit deployment configured, or '' when unset. */
    configuredOrigin: configured,

    /** The origin to publish: the configured one, else wherever we run. */
    publicOrigin: configured || current,

    /** True when the address above is safe to print on a poster. */
    isPublic: !isLocalOrigin(configured || current),

    /** True when the origin was assumed rather than explicitly configured. */
    isAssumed: !configured,

    isLocalOrigin: isLocalOrigin,

    /** Absolute public URL for a path, e.g. url('/track.html'). */
    url: function (path) {
      var base = configured || current;
      if (!path) return base;
      return base + (path.charAt(0) === '/' ? path : '/' + path);
    },
  };
})()
