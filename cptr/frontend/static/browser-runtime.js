(() => {
  const config = window.__cptrBrowser;
  if (!config) return;

  const prefix = `/api/browser/frame/${config.session}`;
  const api = `/api/browser/sessions/${config.session}`;
  const nativeFetch = window.fetch.bind(window);
  const nativeWebSocket = window.WebSocket;

  function remoteUrl(value = location.href) {
    const url = new URL(value, location.href);
    if (url.pathname === prefix) return url.searchParams.get('url') || config.url;
    if (!url.pathname.startsWith(`${prefix}/`)) return config.url;
    const [scheme, encodedHost, ...path] = url.pathname.slice(prefix.length + 1).split('/');
    if (!scheme || !encodedHost) return config.url;
    return `${scheme}://${decodeURIComponent(encodedHost)}/${path.join('/')}${url.search}${url.hash}`;
  }

  function proxyUrl(value, base = remoteUrl()) {
    try {
      const current = new URL(value, location.href);
      if (current.pathname.startsWith(`${prefix}/`)) return `${current.pathname}${current.search}${current.hash}`;
      const url = new URL(value, base);
      if (!/^https?:$/.test(url.protocol)) return value;
      return `${prefix}/${url.protocol.slice(0, -1)}/${encodeURIComponent(url.host)}${url.pathname}${url.search}${url.hash}`;
    } catch {
      return value;
    }
  }

  function report() {
    parent.postMessage({ type: 'cptr-browser-state', url: remoteUrl(), title: document.title }, location.origin);
  }

  const originalPushState = history.pushState.bind(history);
  const originalReplaceState = history.replaceState.bind(history);
  history.pushState = (state, title, url) => {
    const result = originalPushState(state, title, url ? proxyUrl(url) : url);
    queueMicrotask(report);
    return result;
  };
  history.replaceState = (state, title, url) => {
    const result = originalReplaceState(state, title, url ? proxyUrl(url) : url);
    queueMicrotask(report);
    return result;
  };
  addEventListener('popstate', report);
  new MutationObserver(report).observe(document.querySelector('title') || document.head, {
    childList: true,
    subtree: true,
    characterData: true
  });

  window.fetch = (input, init) => {
    if (input instanceof Request) return nativeFetch(new Request(proxyUrl(input.url), input), init);
    return nativeFetch(proxyUrl(input), init);
  };

  const open = XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open = function (method, url, ...rest) {
    return open.call(this, method, proxyUrl(url), ...rest);
  };

  window.WebSocket = function ProxyWebSocket(url, protocols) {
    const scheme = location.protocol === 'https:' ? 'wss' : 'ws';
    const native = new nativeWebSocket(`${scheme}://${location.host}${api}/ws`);
    const proxy = new EventTarget();
    let state = 0;
    let protocol = '';
    Object.defineProperties(proxy, {
      url: { value: String(url) },
      readyState: { get: () => state },
      protocol: { get: () => protocol },
      binaryType: { get: () => native.binaryType, set: (value) => { native.binaryType = value; } },
      onopen: { get: () => proxy._onopen, set: (value) => { proxy._onopen = value; } },
      onmessage: { get: () => proxy._onmessage, set: (value) => { proxy._onmessage = value; } },
      onclose: { get: () => proxy._onclose, set: (value) => { proxy._onclose = value; } },
      onerror: { get: () => proxy._onerror, set: (value) => { proxy._onerror = value; } }
    });
    const emit = (type, event) => {
      proxy.dispatchEvent(event);
      proxy[`_on${type}`]?.call(proxy, event);
    };
    native.addEventListener('open', () => native.send(JSON.stringify({ url: new URL(url, remoteUrl()).href, protocols })));
    native.addEventListener('message', (event) => {
      if (typeof event.data === 'string') {
        try {
          const control = JSON.parse(event.data);
          if (control.type === 'open') {
            state = 1; protocol = control.protocol || ''; emit('open', new Event('open')); return;
          }
        } catch {}
      }
      emit('message', new MessageEvent('message', { data: event.data }));
    });
    native.addEventListener('close', (event) => { state = 3; emit('close', event); });
    native.addEventListener('error', (event) => emit('error', event));
    proxy.send = (data) => {
      if (state !== 1) throw new DOMException('WebSocket is not open', 'InvalidStateError');
      native.send(data);
    };
    proxy.close = (code, reason) => { state = 2; native.close(code, reason); };
    return proxy;
  };
  window.WebSocket.prototype = nativeWebSocket.prototype;

  const NativeEventSource = window.EventSource;
  if (NativeEventSource) {
    window.EventSource = function ProxyEventSource(url, options) {
      return new NativeEventSource(proxyUrl(url), options);
    };
    window.EventSource.prototype = NativeEventSource.prototype;
  }

  document.addEventListener('click', (event) => {
    const link = event.target.closest?.('a[href]');
    if (!link || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    const url = new URL(link.getAttribute('href'), remoteUrl());
    if (!/^https?:$/.test(url.protocol)) return;
    event.preventDefault();
    if (link.target && link.target !== '_self') {
      parent.postMessage({ type: 'cptr-browser-popup', url: url.href }, location.origin);
    } else {
      location.assign(proxyUrl(url.href));
    }
  }, true);

  document.addEventListener('submit', (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement)) return;
    const url = new URL(form.getAttribute('action') || remoteUrl(), remoteUrl());
    if (/^https?:$/.test(url.protocol)) form.action = proxyUrl(url.href);
  }, true);

  const nativeOpen = window.open.bind(window);
  window.open = (url, target, features) => {
    if (url) parent.postMessage({ type: 'cptr-browser-popup', url: new URL(url, remoteUrl()).href }, location.origin);
    return target === '_blank' ? null : nativeOpen(proxyUrl(url || remoteUrl()), target, features);
  };

  report();
})();
