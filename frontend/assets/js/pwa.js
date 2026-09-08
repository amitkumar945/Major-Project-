/**
 * PWA bootstrap: registers the service worker and offers "Install app".
 *
 * Loaded as a plain (non-module) script from every page, so it must not
 * assume any of the app's modules are present. It touches nothing the
 * existing pages own - no globals beyond `window.dsvvPwa`, no DOM changes
 * except the install button it creates itself.
 */
(function () {
  'use strict';

  // A service worker needs a secure context. localhost counts as secure, so
  // development over plain http still works; a LAN IP over http does not, and
  // there the app simply runs as a normal website.
  var secure = window.isSecureContext ||
    location.protocol === 'https:' ||
    location.hostname === 'localhost' ||
    location.hostname === '127.0.0.1';

  var registration = null;

  // ------------------------------------------------------------- register

  if ('serviceWorker' in navigator && secure) {
    window.addEventListener('load', function () {
      navigator.serviceWorker.register('/sw.js', { scope: '/' })
        .then(function (reg) {
          registration = reg;

          // A new worker taking over means the shell changed under a running
          // tab; reload once so the user is not left on half-old assets.
          var refreshing = false;
          navigator.serviceWorker.addEventListener('controllerchange', function () {
            if (refreshing) return;
            refreshing = true;
            location.reload();
          });
        })
        .catch(function (error) {
          // Never fatal: without a worker the site is just a normal website.
          if (window.console && console.warn) {
            console.warn('Service worker registration failed:', error);
          }
        });
    });
  }

  // -------------------------------------------------------- install prompt

  var deferredPrompt = null;

  window.addEventListener('beforeinstallprompt', function (event) {
    // Chrome shows its own mini-infobar by default; take control so the
    // prompt appears where it makes sense in our own UI.
    event.preventDefault();
    deferredPrompt = event;
    showInstallButton();
  });

  window.addEventListener('appinstalled', function () {
    deferredPrompt = null;
    hideInstallButton();
  });

  function isStandalone() {
    return window.matchMedia('(display-mode: standalone)').matches ||
      window.navigator.standalone === true;
  }

  function showInstallButton() {
    if (isStandalone() || document.getElementById('pwa-install')) return;

    var button = document.createElement('button');
    button.id = 'pwa-install';
    button.type = 'button';
    button.setAttribute('aria-label', 'Install this app on your device');
    button.innerHTML =
      '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"' +
      ' stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
      '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>' +
      '<polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>' +
      '<span>Install app</span>';

    button.addEventListener('click', function () {
      if (!deferredPrompt) return;
      deferredPrompt.prompt();
      deferredPrompt.userChoice.then(function () {
        // Either way the prompt is spent and cannot be reused.
        deferredPrompt = null;
        hideInstallButton();
      });
    });

    document.body.appendChild(button);
  }

  function hideInstallButton() {
    var button = document.getElementById('pwa-install');
    if (button && button.parentNode) button.parentNode.removeChild(button);
  }

  // --------------------------------------------------------------- public

  /**
   * Clears cached HTML pages. Called by the app on sign-out so a shared
   * handset cannot page back into the previous user's screens.
   */
  function clearPrivateCache() {
    if (navigator.serviceWorker && navigator.serviceWorker.controller) {
      navigator.serviceWorker.controller.postMessage({ type: 'CLEAR_PRIVATE_CACHE' });
    }
  }

  window.dsvvPwa = {
    clearPrivateCache: clearPrivateCache,
    isStandalone: isStandalone,
    get registration() { return registration; },
  };
})();
