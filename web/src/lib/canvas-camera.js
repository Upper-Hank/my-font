export const clampZoom = value => Math.max(.25, Math.min(2, value));

export function zoomCamera(view, factor, x, y) {
  const zoom = clampZoom(view.zoom * factor), ratio = zoom / view.zoom;
  return { zoom, x: x - (x - view.x) * ratio, y: y - (y - view.y) * ratio };
}

function clampAxis(value, a, b) {
  return Math.min(Math.max(a, b), Math.max(Math.min(a, b), value));
}

// Keep a single sheet on screen: pan freely, but not off into empty space.
export function clampCamera(view, frame, vw, vh, margin = 56) {
  if (!frame || vw <= 0 || vh <= 0) return view;
  const w = frame.width * view.zoom, h = frame.height * view.zoom, left = frame.left * view.zoom, label = 40 * view.zoom;
  return {
    ...view,
    x: clampAxis(view.x, vw - margin - left - w, margin - left),
    y: clampAxis(view.y, vh - margin - h, margin + label),
  };
}

export function isPinchWheel(event) {
  return Boolean(event.ctrlKey || event.metaKey);
}

export function isBrowserZoomKey(event) {
  if (!(event.metaKey || event.ctrlKey) || event.altKey) return false;
  return event.key === '=' || event.key === '+' || event.key === '-' || event.key === '0'
    || event.code === 'Equal' || event.code === 'Minus' || event.code === 'Digit0'
    || event.code === 'NumpadAdd' || event.code === 'NumpadSubtract' || event.code === 'Numpad0';
}

export function visibleFrames(frames, view, width, height, overscan = 240) {
  return frames.filter(frame => {
    const left = frame.left * view.zoom + view.x;
    const right = left + frame.width * view.zoom;
    const top = view.y - 44 * view.zoom;
    const bottom = view.y + frame.height * view.zoom;
    return right >= -overscan && left <= width + overscan && bottom >= -overscan && top <= height + overscan;
  }).map(frame => frame.id);
}

// Coalesce input events without losing deltas, including trackpad bursts.
export function frameScheduler(paint, request = requestAnimationFrame, cancel = cancelAnimationFrame) {
  let pending = null;
  return {
    schedule() {
      if (pending === null) pending = request(() => { pending = null; paint(); });
    },
    cancel() { if (pending !== null) cancel(pending); pending = null; },
  };
}
