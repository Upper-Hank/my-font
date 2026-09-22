import { test } from 'node:test';
import assert from 'node:assert/strict';
import { geometry, isDirtyDoc, makePage, nextEmpty, persistableDoc, placeChars, placeFromLibrary } from './template-canvas.js';

test('shared blocks can be placed repeatedly without consuming or moving earlier copies', () => {
  const source = [{ id: 'library-23383', char: '字' }];
  const page = makePage();
  const original = { pages: [page], library: [] };
  const once = placeFromLibrary(original, source, [source[0].id], page.id);
  const twice = placeFromLibrary(once, source, [source[0].id], page.id);
  assert.equal(source.length, 1);
  assert.equal(original.pages[0].cells.length, 0);
  assert.deepEqual(twice.pages[0].cells.map(c => c.char), ['字', '字']);
  assert.equal(new Set(twice.pages[0].cells.map(c => c.id)).size, 2);
  assert.deepEqual(twice.pages[0].cells.map(c => c.slot), [0, 1]);
  const fresh = placeFromLibrary({ pages: [makePage()], library: [] }, source, [], null);
  assert.equal(fresh.pages[0].cells.length, 0);
  const removed = placeFromLibrary(twice, source, [twice.pages[0].cells[0].id], null);
  assert.equal(removed.pages[0].cells.length, 1);
  assert.equal(source[0].char, '字');
});

test('typed strings fill empty slots in reading order, keep repeats, and grow pages', () => {
  const page = { ...makePage('portrait', 20), format: 'A5' };
  page.cells = [{ id: 'keep', char: '已', slot: 1 }];
  const start = { pages: [page], library: [] };
  const first = placeChars(start, ['春', '春', '风'], page.id, 0);
  assert.deepEqual(first.doc.pages[0].cells.sort((a, b) => a.slot - b.slot).map(c => [c.slot, c.char]), [[0, '春'], [1, '已'], [2, '春'], [3, '风']]);
  assert.equal(first.doc.pages[0].cells.find(c => c.id === 'keep').char, '已');
  assert.deepEqual(first.caret, { pageId: page.id, slot: 4 });
  const capacity = geometry(page).capacity;
  const many = Array.from({ length: capacity + 1 }, () => '字');
  const grown = placeChars({ pages: [{ ...makePage('portrait', 20), format: 'A5', cells: [] }], library: [] }, many, null, 0);
  assert.equal(grown.doc.pages.length, 2);
  assert.equal(grown.doc.pages[0].cells.length, capacity);
  assert.equal(grown.doc.pages[1].cells.length, 1);
  assert.equal(grown.created.length, 1);
  assert.equal(nextEmpty(first.doc, page.id, 0).slot, 4);
});

test('A3 cells stay inside the page margins including the 2 mm frame', () => {
  const geo = geometry({ size: 16, format: 'A3', orientation: 'portrait' });
  const outer = geo.slots.map(slot => ({ left: slot.x - 2, top: slot.y - 2, right: slot.x + 16 + 2, bottom: slot.y + 16 + 2 }));
  assert.equal(geo.columns, 11);
  assert.equal(geo.rows, 13);
  assert.ok(outer.every(box => box.left >= 24 && box.right <= geo.width - 24 && box.top >= 42 && box.bottom <= geo.height - 18));
  assert.ok(geo.guide.x <= Math.min(...outer.map(box => box.left)));
  assert.ok(geo.guide.y <= Math.min(...outer.map(box => box.top)));
  assert.ok(geo.guide.x + geo.guide.w >= Math.max(...outer.map(box => box.right)));
  assert.ok(geo.guide.y + geo.guide.h >= Math.max(...outer.map(box => box.bottom)));
});

test('leave warning only counts document edits, not identical snapshots', () => {
  const page = { ...makePage(), cells: [{ id: 'a', char: '字', slot: 1 }, { id: 'b', char: '己', slot: 0 }] };
  const doc = { title: '通用书写纸', mode: 'generic', pages: [page, makePage()], library: [] };
  const baseline = persistableDoc(doc);
  assert.equal(isDirtyDoc(doc, baseline), false);
  assert.equal(isDirtyDoc({ ...doc, title: '别的名字' }, baseline), true);
  assert.equal(isDirtyDoc({ ...doc, pages: [{ ...page, format: 'A3' }] }, baseline), true);
  assert.equal(isDirtyDoc({ ...doc, pages: [{ ...page, cells: [...page.cells].reverse() }] }, baseline), false);
  assert.equal(isDirtyDoc(doc, null), false);
});
