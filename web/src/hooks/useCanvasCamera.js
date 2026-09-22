import { useCallback, useLayoutEffect, useRef, useState } from 'react';
import { frameScheduler, visibleFrames } from '../lib/canvas-camera.js';

// Camera motion only writes compositor transforms. React updates when the set of
// visible pages changes, not on every pointer/wheel event or zoom percentage.
export default function useCanvasCamera(viewport, frames, ready) {
  const view = useRef({ x: 60, y: 70, zoom: .65 });
  const world = useRef(null);
  const zoomLabel = useRef(null);
  const zoomIn = useRef(null);
  const zoomOut = useRef(null);
  const scheduler = useRef(null);
  const bounds = useRef({ width: 0, height: 0 });
  const [visible, setVisible] = useState([]);

  useLayoutEffect(() => {
    const el = viewport.current;
    if (!ready || !el) return;
    let lastZoom;
    const paint = () => {
      const v = view.current;
      if (world.current) world.current.style.transform = `translate3d(${v.x}px, ${v.y}px, 0) scale(${v.zoom})`;
      if (lastZoom !== v.zoom) {
        if (zoomLabel.current) zoomLabel.current.textContent = `${Math.round(v.zoom * 100)}%`;
        if (zoomIn.current) zoomIn.current.disabled = v.zoom >= 2;
        if (zoomOut.current) zoomOut.current.disabled = v.zoom <= .25;
        lastZoom = v.zoom;
      }
      const next = visibleFrames(frames, v, bounds.current.width, bounds.current.height);
      setVisible(previous => previous.length === next.length && previous.every((id, i) => id === next[i]) ? previous : next);
    };
    const task = frameScheduler(paint);
    scheduler.current = task;
    const measure = () => { bounds.current = { width: el.clientWidth, height: el.clientHeight }; task.schedule(); };
    const observer = new ResizeObserver(measure);
    observer.observe(el);
    measure();
    // Apply the stored camera before the first paint, also after loading a task.
    paint();
    return () => { observer.disconnect(); task.cancel(); scheduler.current = null; };
  }, [viewport, frames, ready]);

  const setView = useCallback(update => {
    view.current = typeof update === 'function' ? update(view.current) : update;
    scheduler.current?.schedule();
  }, []);
  return { view, setView, world, zoomLabel, zoomIn, zoomOut, visible };
}
