import { test } from 'node:test';
import assert from 'node:assert/strict';
import { clampCamera, frameScheduler, isBrowserZoomKey, isPinchWheel, visibleFrames, zoomCamera } from './canvas-camera.js';
import { geometry } from './template-canvas.js';

test('input bursts paint once per frame, retain the latest camera, and cancel on unmount', () => {
  const queue = new Map();
  let serial = 0, paints = 0, view = { x: 0, y: 0, zoom: 1 }, painted;
  const scheduler = frameScheduler(() => { paints++; painted = view; }, callback => { queue.set(++serial, callback); return serial; }, id => queue.delete(id));
  for (let i = 0; i < 120; i++) { view = { ...view, x: view.x + 1 }; scheduler.schedule(); }
  assert.equal(queue.size, 1);
  const callback = queue.values().next().value; queue.clear(); callback();
  assert.equal(paints, 1);
  assert.equal(painted.x, 120);
  scheduler.schedule(); scheduler.cancel();
  assert.equal(queue.size, 0);
});

test('culling retains only nearby pages and cursor zoom preserves world coordinates', () => {
  const frames = Array.from({ length: 30 }, (_, i) => ({ id: String(i), left: i * 991, width: 891, height: 1260 }));
  assert.deepEqual(visibleFrames(frames, { x: 0, y: 0, zoom: 1 }, 900, 800), ['0', '1']);
  assert.deepEqual(visibleFrames(frames, { x: -9910, y: 0, zoom: 1 }, 900, 800), ['9', '10', '11']);
  assert.deepEqual(visibleFrames(frames, { x: 0, y: -3000, zoom: 1 }, 900, 800), []);
  const view = { x: -180, y: 85, zoom: .6 };
  for (const factor of [.001, 1.4, 100]) {
    const zoomed = zoomCamera(view, factor, 320, 240);
    assert.ok(zoomed.zoom >= .25 && zoomed.zoom <= 2);
    assert.ok(Math.abs((320-view.x)/view.zoom - (320-zoomed.x)/zoomed.zoom) < 1e-9);
    assert.ok(Math.abs((240-view.y)/view.zoom - (240-zoomed.y)/zoomed.zoom) < 1e-9);
  }
  assert.equal(geometry({size:10, format:'A3', orientation:'portrait'}), geometry({size:10, format:'A3', orientation:'portrait'}));
});

test('paper pan stays inside the viewport instead of drifting into empty space', () => {
  const frame = { left: 0, width: 891, height: 1260 };
  const fitted = clampCamera({ x: 200, y: 80, zoom: .4 }, frame, 800, 700);
  assert.equal(clampCamera({ x: 4000, y: 80, zoom: .4 }, frame, 800, 700).x, clampCamera({ x: fitted.x + 4000, y: 80, zoom: .4 }, frame, 800, 700).x);
  assert.equal(clampCamera({ x: -4000, y: 80, zoom: .4 }, frame, 800, 700).x, clampCamera({ x: fitted.x - 4000, y: 80, zoom: .4 }, frame, 800, 700).x);
  const tight = clampCamera({ x: 0, y: 0, zoom: 2 }, frame, 400, 300);
  const farther = clampCamera({ x: -99999, y: -99999, zoom: 2 }, frame, 400, 300);
  assert.equal(farther.x, clampCamera({ x: farther.x - 10, y: farther.y, zoom: 2 }, frame, 400, 300).x);
  assert.equal(farther.y, clampCamera({ x: farther.x, y: farther.y - 10, zoom: 2 }, frame, 400, 300).y);
  assert.notEqual(farther.x, tight.x);
  assert.notEqual(farther.y, tight.y);
});

test('trackpad pinch and browser zoom shortcuts are captured for the canvas', () => {
  assert.equal(isPinchWheel({ ctrlKey: true, metaKey: false }), true);
  assert.equal(isPinchWheel({ ctrlKey: false, metaKey: true }), true);
  assert.equal(isPinchWheel({ ctrlKey: false, metaKey: false }), false);
  assert.equal(isBrowserZoomKey({ metaKey: true, altKey: false, key: '+', code: 'Equal' }), true);
  assert.equal(isBrowserZoomKey({ ctrlKey: true, altKey: false, key: '-', code: 'Minus' }), true);
  assert.equal(isBrowserZoomKey({ metaKey: true, altKey: false, key: '0', code: 'Digit0' }), true);
  assert.equal(isBrowserZoomKey({ metaKey: false, ctrlKey: false, altKey: false, key: '+', code: 'Equal' }), false);
});
