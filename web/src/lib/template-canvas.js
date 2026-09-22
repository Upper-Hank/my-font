export const uid = () => crypto.randomUUID();
export const makePage = (orientation = 'portrait', size = 16) => ({ id: uid(), orientation, size, format: 'A4', cells: [] });
const FRAME_MM = 2;
const geometryCache = new Map();
export function geometry(page) {
  const key = `${page.format || 'A4'}:${page.orientation}:${page.size}`;
  if (geometryCache.has(key)) return geometryCache.get(key);
  const dimensions = { A5: [148, 210], A4: [210, 297], A3: [297, 420] }[page.format || 'A4'];
  const [width, height] = page.orientation === 'landscape' ? [...dimensions].reverse() : dimensions;
  const columns = Math.max(1, Math.floor((width - 48 + 6) / (page.size + 6)));
  const rows = Math.max(1, Math.floor((height - 60 + 12 - 8) / (page.size + 12)));
  const gridW = columns * page.size + (columns - 1) * 6;
  const gridH = rows * page.size + (rows - 1) * 12 + 8;
  let x = 24 + (width - 48 - gridW) / 2;
  let y = 42 + (height - 60 - gridH) / 2;
  // Cell strokes extend FRAME_MM past the writing box; keep them inside the page margins.
  x = Math.min(Math.max(x, 24 + FRAME_MM), width - 24 - FRAME_MM - gridW);
  y = Math.min(Math.max(y, 42 + FRAME_MM), height - 18 - FRAME_MM - (gridH - 8));
  const result = {
    width, height, columns, rows, capacity: columns * rows,
    guide: { x: x - FRAME_MM, y: y - FRAME_MM, w: gridW + FRAME_MM * 2, h: rows * page.size + (rows - 1) * 12 + FRAME_MM * 2 },
    slots: Array.from({ length: columns * rows }, (_, i) => ({ x: x + i % columns * (page.size + 6), y: y + Math.floor(i / columns) * (page.size + 12) })),
  };
  if (geometryCache.size >= 128) geometryCache.clear();
  geometryCache.set(key, result);
  return result;
}
// Move blocks atomically; occupied destinations swap for a single page block.
export function transfer(doc, ids, pageId, slot = 0) {
  const all = [...doc.library, ...doc.pages.flatMap(p => p.cells)];
  const moving = ids.map(id => all.find(c => c.id === id)).filter(Boolean);
  if (!moving.length) return doc;
  const picked = new Set(ids);
  const target = doc.pages.find(p => p.id === pageId);
  const source = moving.length === 1 ? doc.pages.find(p => p.cells.some(c => c.id === moving[0].id)) : null;
  const occupied = target?.cells.find(c => c.slot === slot && !picked.has(c.id));
  if (occupied && source) {
    return { ...doc, pages: doc.pages.map(p => ({ ...p, cells: p.cells.map(c => c.id === moving[0].id ? { ...occupied, slot: c.slot } : c.id === occupied.id ? { ...moving[0], slot: c.slot } : c) })) };
  }
  const next = { ...doc, library: doc.library.filter(c => !picked.has(c.id)), pages: doc.pages.map(p => ({ ...p, cells: p.cells.filter(c => !picked.has(c.id)) })) };
  if (!target) { next.library.push(...moving.map(({ id, char }) => ({ id, char }))); return next; }
  const page = next.pages.find(p => p.id === pageId);
  const used = new Set(page.cells.map(c => c.slot));
  const capacity = geometry(page).capacity;
  const available = Array.from({ length: capacity }, (_, i) => (i + slot) % capacity).filter(i => !used.has(i));
  if (available.length < moving.length) throw new Error('页面空间不足，请新增页面或把部分字块拖回字块库。');
  page.cells.push(...moving.map((c, i) => ({ ...c, slot: available[i] })));
  return next;
}
export function resizePages(doc, ids, patch) {
  const overflow = [];
  const pages = doc.pages.map(p => {
    if (!ids.includes(p.id)) return p;
    const next = { ...p, ...patch };
    const capacity = geometry(next).capacity;
    next.cells = p.cells.filter(c => { if (c.slot < capacity) return true; overflow.push({ id: c.id, char: c.char }); return false; });
    return next;
  });
  return { ...doc, pages, library: [...doc.library, ...overflow] };
}

// Catalog entries are reusable sources. Only page instances are moved.
export function placeFromLibrary(doc, library, ids, pageId, slot = 0) {
  const sources = new Map(library.map(block => [block.id, block]));
  const copies = [];
  const moving = ids.flatMap(id => {
    if (!sources.has(id)) return [id];
    if (!pageId) return [];
    const copy = { id: uid(), char: sources.get(id).char };
    copies.push(copy);
    return [copy.id];
  });
  return transfer({ ...doc, library: [...doc.library, ...copies] }, moving, pageId, slot);
}

function pageCapacity(page) {
  return geometry(page).capacity;
}

function unusedSlots(page, from = 0) {
  const used = new Set(page.cells.map(c => c.slot));
  const slots = [];
  for (let i = from; i < pageCapacity(page); i++) if (!used.has(i)) slots.push(i);
  return slots;
}

export function nextEmpty(doc, pageId, slot = 0) {
  const pages = doc.pages;
  if (!pages.length) return null;
  let index = pages.findIndex(p => p.id === pageId);
  if (index < 0) index = 0;
  for (let i = index; i < pages.length; i++) {
    const start = i === index ? slot : 0;
    const empty = unusedSlots(pages[i], start);
    if (empty.length) return { pageId: pages[i].id, slot: empty[0] };
  }
  return { pageId: pages.at(-1).id, slot: 0 };
}

// Fill empty slots in reading order from a caret. Occupied cells stay put; extra pages match the last page.
export function placeChars(doc, chars, pageId, slot = 0) {
  if (!chars.length) return { doc, ids: [], caret: nextEmpty(doc, pageId, slot), created: [] };
  const pages = doc.pages.map(p => ({ ...p, cells: [...p.cells] }));
  if (!pages.length) pages.push(makePage());
  const existing = pages.reduce((n, p) => n + p.cells.length, 0);
  if (existing + chars.length > 1000) throw new Error('每个模板最多 1000 个字块。');
  let index = pages.findIndex(p => p.id === pageId);
  if (index < 0) index = 0;
  let from = slot;
  let n = 0;
  const ids = [];
  const created = [];
  while (n < chars.length) {
    if (index >= pages.length) {
      if (pages.length >= 30) throw new Error('空格不足，已达 30 页。请分批放置。');
      const last = pages.at(-1);
      const page = { ...makePage(last.orientation, last.size), format: last.format || 'A4' };
      pages.push(page);
      created.push(page.id);
    }
    const page = pages[index];
    const empty = unusedSlots(page, from);
    if (!empty.length) { index += 1; from = 0; continue; }
    for (const at of empty) {
      if (n >= chars.length) break;
      const id = uid();
      page.cells.push({ id, char: chars[n], slot: at });
      ids.push(id);
      n += 1;
    }
    index += 1;
    from = 0;
  }
  const lastCell = pages.flatMap(p => p.cells).find(c => c.id === ids.at(-1));
  const lastPage = pages.find(p => p.cells.some(c => c.id === lastCell.id));
  return { doc: { ...doc, pages }, ids, caret: nextEmpty({ ...doc, pages }, lastPage.id, lastCell.slot + 1) || { pageId: lastPage.id, slot: lastCell.slot }, created };
}

export function persistableDoc(doc) {
  const generic = (doc.mode || 'assigned') === 'generic';
  return {
    title: doc.title || '',
    mode: generic ? 'generic' : 'assigned',
    pages: (generic ? doc.pages.slice(0, 1) : doc.pages).map(p => ({
      format: p.format || 'A4',
      orientation: p.orientation || 'portrait',
      size: p.size,
      cells: [...p.cells].sort((a, b) => a.slot - b.slot).map(c => ({ slot: c.slot, char: c.char })),
    })),
  };
}

export function isDirtyDoc(doc, baseline) {
  return Boolean(baseline) && JSON.stringify(persistableDoc(doc)) !== JSON.stringify(baseline);
}
