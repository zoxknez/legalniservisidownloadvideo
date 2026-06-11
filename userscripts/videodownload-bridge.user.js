// ==UserScript==
// @name         Video Download Servisi — Bridge (Sniffer + Sesije)
// @namespace    https://github.com/videodownloadservisi
// @version      2.1.1
// @description  Automatski šalje sesije i snifuje MPD/license URL-ove u lokalnu aplikaciju.
// @author       Video Download Servisi
// @match        *://*.max.com/*
// @match        *://*.hbomax.com/*
// @match        *://*.voyo.rs/*
// @match        *://*.voyo.hr/*
// @match        *://*.rtl.hr/*
// @match        *://*.rtsplaneta.rs/*
// @match        *://*.hrt.hr/*
// @match        *://*.eon.tv/*
// @match        *://*.skyshowtime.com/*
// @match        *://*.skyott.com/*
// @grant        GM_xmlhttpRequest
// @connect      127.0.0.1
// @connect      localhost
// @run-at       document-start
// ==/UserScript==

(function () {
  'use strict';

  const BACKEND = '__BACKEND_URL__';
  const BRIDGE_TOKEN = '__BRIDGE_TOKEN__';
  const SESSION_URL = BACKEND + '/api/bridge/session';
  const SNIFFER_URL = BACKEND + '/api/bridge/sniffer';
  const SESSION_INTERVAL_MS = 3 * 60 * 1000;
  const SESSION_POLL_MS = 45 * 1000;

  let lastSessionHash = '';

  function log(msg, data) {
    console.log('[VDS Bridge] ' + msg, data || '');
  }

  function getService() {
    const host = window.location.hostname;
    if (host.includes('max.com') || host.includes('hbomax.com')) return 'hbomax';
    if (host.includes('voyo.')) return 'voyo';
    if (host.includes('rtsplaneta')) return 'rtsplaneta';
    if (host.includes('hrt.hr')) return 'hrti';
    if (host.includes('eon.tv')) return 'eon';
    if (host.includes('skyshowtime.com') || host.includes('skyott.com')) return 'skyshowtime';
    return 'unknown';
  }

  function postJson(url, body, onOk) {
    GM_xmlhttpRequest({
      method: 'POST',
      url: url,
      headers: { 'Content-Type': 'application/json', 'X-VDS-Bridge-Token': BRIDGE_TOKEN },
      data: JSON.stringify(body),
      onload: function (res) {
        if (res.status >= 200 && res.status < 300) {
          try {
            onOk && onOk(JSON.parse(res.responseText || '{}'));
          } catch (e) {
            onOk && onOk({});
          }
        } else {
          log('HTTP ' + res.status, res.responseText);
        }
      },
      onerror: function (err) {
        log('Request failed (je li run.py pokrenut?)', err);
      },
    });
  }

  function decodeJwtPayload(token) {
    try {
      const part = String(token).replace(/^(Bearer|Client)\s+/i, '').split('.')[1];
      if (!part) return {};
      return JSON.parse(atob(part.replace(/-/g, '+').replace(/_/g, '/')));
    } catch (e) {
      return {};
    }
  }

  function findNestedValue(value, keyRx, depth) {
    if (!value || depth > 6 || typeof value !== 'object') return '';
    if (Array.isArray(value)) {
      for (const item of value) {
        const found = findNestedValue(item, keyRx, depth + 1);
        if (found) return found;
      }
      return '';
    }
    for (const key in value) {
      const val = value[key];
      if (keyRx.test(key) && val != null && typeof val !== 'object') {
        return String(val).trim();
      }
    }
    for (const key in value) {
      const found = findNestedValue(value[key], keyRx, depth + 1);
      if (found) return found;
    }
    return '';
  }

  function scanLocalStorage(keyRx) {
    for (let i = 0; i < localStorage.length; i += 1) {
      const key = localStorage.key(i) || '';
      const val = localStorage.getItem(key) || '';
      if (keyRx.test(key) && val) return val.trim();
      try {
        const found = findNestedValue(JSON.parse(val), keyRx, 0);
        if (found) return found;
      } catch (e) {
        /* ignore */
      }
    }
    return '';
  }

  function collectHrtiSession() {
    const token = localStorage.getItem('token') || '';
    if (!token || token.length <= 8) return '';
    const payload = decodeJwtPayload(token);
    const cidRx = /^(customerid|customer_id|userid|user_id|customerreferenceid|customer_reference_id)$/i;
    const emailRx = /^(email|username|useremail|mail)$/i;
    const customerId =
      findNestedValue(
        payload,
        /^(customerid|customer_id|userid|user_id|customerreferenceid|customer_reference_id|sub)$/i,
        0
      ) || scanLocalStorage(cidRx);
    const email = findNestedValue(payload, emailRx, 0) || scanLocalStorage(emailRx);
    const out = { token: token };
    if (customerId) out.customer_id = customerId;
    if (email) out.email = email;
    return JSON.stringify(out);
  }

  function collectSessions() {
    const batch = {};
    const host = window.location.hostname;

    if (host.includes('voyo.')) {
      const t =
        localStorage.getItem('token') ||
        localStorage.getItem('apollo-cache-persist') ||
        '';
      if (t && t.length > 8) {
        let variant = 'rs';
        if (host.includes('voyo.hr') || host.includes('rtl.hr')) {
          variant = 'hr';
        }
        if (t.trim().startsWith('{')) {
          try {
            const parsed = JSON.parse(t);
            parsed.variant = variant;
            batch.voyo = JSON.stringify(parsed);
          } catch (e) {
            batch.voyo = JSON.stringify({ token: t, variant: variant });
          }
        } else {
          batch.voyo = JSON.stringify({ token: t, variant: variant });
        }
      }
    }
    if (host.includes('hrt.hr')) {
      const session = collectHrtiSession();
      if (session) batch.hrti = session;
    }
    if (host.includes('rtsplaneta')) {
      const k = Object.keys(localStorage).find(function (x) {
        return /token|auth/i.test(x);
      });
      const t = k ? localStorage.getItem(k) : '';
      if (t && t.length > 8) batch.rtsplaneta = t;
    }
    if (host.includes('max.com') || host.includes('hbomax.com')) {
      const t = localStorage.getItem('token') || '';
      if (t && t.length > 8) batch.hbomax = t;
    }
    if (host.includes('skyshowtime.com') || host.includes('skyott.com')) {
      const cookies = {};
      const raw = document.cookie || '';
      if (raw) {
        raw.split(';').forEach(function (part) {
          const eq = part.indexOf('=');
          if (eq < 1) return;
          const name = part.slice(0, eq).trim();
          const val = part.slice(eq + 1).trim();
          if (name) {
            try {
              cookies[name] = decodeURIComponent(val.replace(/\+/g, ' '));
            } catch (e) {
              cookies[name] = val;
            }
          }
        });
      }
      if (Object.keys(cookies).length) {
        batch.skyshowtime = JSON.stringify({ cookies: cookies });
      }
    }
    if (host.includes('eon.tv')) {
      const cookies = {};
      const raw = document.cookie || '';
      if (raw) {
        raw.split(';').forEach(function (part) {
          const eq = part.indexOf('=');
          if (eq < 1) return;
          const name = part.slice(0, eq).trim();
          const val = part.slice(eq + 1).trim();
          if (name) {
            try {
              cookies[name] = decodeURIComponent(val.replace(/\+/g, ' '));
            } catch (e) {
              cookies[name] = val;
            }
          }
        });
      }
      if (Object.keys(cookies).length) {
        batch.eon = JSON.stringify({ cookies: cookies });
      }
    }

    return batch;
  }

  function hashBatch(batch) {
    try {
      return JSON.stringify(batch);
    } catch (e) {
      return '';
    }
  }

  function pushSessions(reason) {
    const batch = collectSessions();
    const keys = Object.keys(batch);
    if (!keys.length) return;

    const h = hashBatch(batch);
    if (h === lastSessionHash && reason !== 'manual') return;
    lastSessionHash = h;

    postJson(SESSION_URL, { batch: batch, source: 'userscript', reason: reason || 'auto' }, function (res) {
      if (res.success) {
        log('Sesija poslata (' + (res.message || keys.join(', ')) + ')');
        showBadge('✓ Sesija sinhronizovana', '#10b981');
      }
    });
  }

  function showBadge(text, color) {
    try {
      let el = document.getElementById('vds-bridge-badge');
      if (!el) {
        el = document.createElement('div');
        el.id = 'vds-bridge-badge';
        el.style.cssText =
          'position:fixed;bottom:16px;right:16px;z-index:2147483647;padding:8px 14px;border-radius:8px;font:600 12px system-ui,sans-serif;color:#fff;box-shadow:0 4px 20px rgba(0,0,0,.4);pointer-events:none;transition:opacity .4s';
        document.documentElement.appendChild(el);
      }
      el.textContent = text;
      el.style.background = color || '#6366f1';
      el.style.opacity = '1';
      clearTimeout(el._t);
      el._t = setTimeout(function () {
        el.style.opacity = '0';
      }, 3500);
    } catch (e) {
      /* ignore */
    }
  }

  function sendSniffer(type, url, headers) {
    const service = getService();
    if (service === 'unknown' || !url) return;

    const cleanHeaders = {};
    const keep = [
      'authorization',
      'x-dt-custom-data',
      'x-ax-drm-message',
      'drm-token',
      'deviceid',
      'devicetypeid',
      'x-license-token',
    ];
    if (headers) {
      Object.keys(headers).forEach(function (key) {
        if (keep.indexOf(key.toLowerCase()) >= 0) {
          cleanHeaders[key] = headers[key];
        }
      });
    }

    postJson(
      SNIFFER_URL,
      {
        service: service,
        type: type,
        url: url,
        headers: cleanHeaders,
        title: document.title || '',
      },
      function () {
        showBadge('⚡ ' + type + ' poslat u app', '#6366f1');
      }
    );
  }

  function inspectUrl(url, headers) {
    if (!url) return;
    const low = String(url).toLowerCase();
    if (low.includes('.mpd') || low.includes('.m3u8') || low.includes('/manifest')) {
      sendSniffer('manifest', url, headers);
    } else if (
      low.includes('widevine') ||
      low.includes('license') ||
      low.includes('/drm') ||
      low.includes('challenge')
    ) {
      sendSniffer('license', url, headers);
    }
  }

  // ── fetch hook ──
  const originalFetch = window.fetch;
  window.fetch = async function () {
    const args = arguments;
    const url =
      typeof args[0] === 'string'
        ? args[0]
        : args[0] instanceof URL
          ? args[0].href
          : args[0] && args[0].url
            ? args[0].url
            : '';
    const options = args[1] || {};
    inspectUrl(url, options.headers || {});
    return originalFetch.apply(this, args);
  };

  // ── XHR hook ──
  const originalOpen = XMLHttpRequest.prototype.open;
  const originalSend = XMLHttpRequest.prototype.send;
  const originalSetRequestHeader = XMLHttpRequest.prototype.setRequestHeader;

  XMLHttpRequest.prototype.open = function (method, url) {
    this._vdsUrl = url;
    this._vdsHeaders = {};
    return originalOpen.apply(this, arguments);
  };

  XMLHttpRequest.prototype.setRequestHeader = function (header, value) {
    this._vdsHeaders = this._vdsHeaders || {};
    this._vdsHeaders[header] = value;
    return originalSetRequestHeader.apply(this, arguments);
  };

  XMLHttpRequest.prototype.send = function (body) {
    inspectUrl(this._vdsUrl, this._vdsHeaders || {});
    return originalSend.apply(this, arguments);
  };

  // ── Session sync schedule ──
  function scheduleSessionSync() {
    setTimeout(function () {
      pushSessions('pageload');
    }, 2500);
    setInterval(function () {
      pushSessions('interval');
    }, SESSION_INTERVAL_MS);
    setInterval(function () {
      pushSessions('poll');
    }, SESSION_POLL_MS);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', scheduleSessionSync);
  } else {
    scheduleSessionSync();
  }

  log('Aktivan — backend: ' + BACKEND);
})();
