// Learn more: https://github.com/testing-library/jest-dom
import '@testing-library/jest-dom'

// Polyfill global.fetch for jsdom so test files can jest.spyOn(global, 'fetch').
// jest.spyOn requires the property to exist on the target object.
// The test's mockImplementation overrides this — we just need the property present.
if (typeof global.fetch === 'undefined') {
  global.fetch = function fakeFetch() {
    return Promise.resolve({
      ok: true,
      status: 200,
      json: () => Promise.resolve({}),
      text: () => Promise.resolve('{}'),
      headers: new (typeof Headers !== 'undefined' ? Headers : Object)(),
    });
  };
}

// Polyfill Response for jsdom if not available (needed by AC-11 fetch spy)
if (typeof global.Response === 'undefined') {
  global.Response = class Response {
    constructor(body, init = {}) {
      this._body = body || '';
      this.status = init.status || 200;
      this.ok = this.status >= 200 && this.status < 300;
      this.headers = new (typeof Headers !== 'undefined' ? Headers : Object)();
    }
    json() { return Promise.resolve(JSON.parse(this._body || '{}')); }
    text() { return Promise.resolve(this._body || ''); }
  };
}

// Polyfill ResizeObserver for jsdom (used by RSI canvas)
if (typeof global.ResizeObserver === 'undefined') {
  global.ResizeObserver = class ResizeObserver {
    constructor(cb) { this._cb = cb; }
    observe() {}
    unobserve() {}
    disconnect() {}
  };
}

// Stub HTMLCanvasElement.getContext for jsdom (no canvas npm needed)
// Returns a mock 2d context that silently no-ops all draw calls.
if (typeof HTMLCanvasElement !== 'undefined') {
  const origGetContext = HTMLCanvasElement.prototype.getContext;
  HTMLCanvasElement.prototype.getContext = function (type, ...args) {
    if (type === '2d') {
      return {
        fillRect: () => {},
        clearRect: () => {},
        getImageData: (x, y, w, h) => ({ data: new Array(w * h * 4).fill(0) }),
        putImageData: () => {},
        createImageData: () => ([]),
        setTransform: () => {},
        drawImage: () => {},
        save: () => {},
        fillText: () => {},
        restore: () => {},
        beginPath: () => {},
        moveTo: () => {},
        lineTo: () => {},
        closePath: () => {},
        stroke: () => {},
        translate: () => {},
        scale: () => {},
        rotate: () => {},
        arc: () => {},
        fill: () => {},
        measureText: () => ({ width: 0 }),
        transform: () => {},
        rect: () => {},
        clip: () => {},
        canvas: this,
        fillStyle: '',
        strokeStyle: '',
        lineWidth: 1,
        globalAlpha: 1,
      };
    }
    return origGetContext.call(this, type, ...args);
  };
}


