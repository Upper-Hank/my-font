import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { getJson, postJson } from '../api.js';
import { ConfirmDialog, Disclosure, ErrorNote, iconSm } from '../ui.jsx';
import { useHeaderBack } from '../components/HeaderBack.jsx';
import CheckIcon from '@uplus-icon/react/icons/check';
import ChevronDownIcon from '@uplus-icon/react/icons/chevron-down';
import ChevronRightIcon from '@uplus-icon/react/icons/chevron-right';
import CloseIcon from '@uplus-icon/react/icons/close';
import CursorIcon from '@uplus-icon/react/icons/cursor';
import DownloadIcon from '@uplus-icon/react/icons/download';
import DuplicateIcon from '@uplus-icon/react/icons/duplicate';
import FileIcon from '@uplus-icon/react/icons/file';
import FloppyDiskIcon from '@uplus-icon/react/icons/floppy-disk';
import FolderIcon from '@uplus-icon/react/icons/folder';
import GridIcon from '@uplus-icon/react/icons/grid';
import HandIcon from '@uplus-icon/react/icons/hand';
import KeyboardIcon from '@uplus-icon/react/icons/keyboard';
import PencilIcon from '@uplus-icon/react/icons/pencil';
import PlusIcon from '@uplus-icon/react/icons/plus';
import RedoIcon from '@uplus-icon/react/icons/redo';
import RulerIcon from '@uplus-icon/react/icons/ruler';
import TargetIcon from '@uplus-icon/react/icons/target';
import TrashIcon from '@uplus-icon/react/icons/trash';
import UndoIcon from '@uplus-icon/react/icons/undo';
import ZoomInIcon from '@uplus-icon/react/icons/zoom-in';
import ZoomOutIcon from '@uplus-icon/react/icons/zoom-out';
import SelectMenu from '../SelectMenu.jsx';
import { parseCells } from '../lib/template-editor.js';
import { geometry, isDirtyDoc, makePage, nextEmpty, persistableDoc, placeChars, placeFromLibrary, resizePages, uid } from '../lib/template-canvas.js';
import { clampCamera, clampZoom, isBrowserZoomKey, isPinchWheel, zoomCamera } from '../lib/canvas-camera.js';
import useCanvasCamera from '../hooks/useCanvasCamera.js';
import CanvasFrame from '../components/CanvasFrame.jsx';

const DRAFT = 'handfont-canvas-v2';
const code = char => `U+${char.codePointAt(0).toString(16).toUpperCase().padStart(4, '0')}`;

function downloadTemplatePdf(name) {
  const link = document.createElement('a');
  link.href = `/download?p=templates/${encodeURIComponent(name)}/template.pdf`;
  link.download = 'template.pdf';
  link.rel = 'noopener';
  document.body.append(link);
  link.click();
  link.remove();
}

export default function Templates({ resumeDraft = false }) {
  const { id } = useParams();
  const recordId = id && id !== 'new' && id !== 'draft' ? id : '';
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const requestedChars = params.get("chars") || "";
  const [catalog, setCatalog] = useState([]);
  const [libraryQuery, setLibraryQuery] = useState('');
  const [placementFilter, setPlacementFilter] = useState('all');
  const [glyphFilter, setGlyphFilter] = useState('all');
  const [libraryLimit, setLibraryLimit] = useState(120);
  const [data, setData] = useState(null);
  const [doc, setDoc] = useState({ title: '我的书写模板', pages: [], library: [] });
  const [pages, setPages] = useState([]);
  const [selection, setSelection] = useState([]);
  const [bulk, setBulk] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [busyKind, setBusyKind] = useState('');
  const [baseline, setBaseline] = useState(null);
  const [leaveOpen, setLeaveOpen] = useState(false);
  const [past, setPast] = useState([]);
  const [future, setFuture] = useState([]);
  const [tool, setTool] = useState('select');
  const [caret, setCaret] = useState(null);
  const [typeText, setTypeText] = useState('');
  const [guides, setGuides] = useState(true);
  const [openPages, setOpenPages] = useState([]);
  const [panning, setPanning] = useState(false);
  const [addCharsOpen, setAddCharsOpen] = useState(false);
  const dropTarget = useRef(null);
  const [editing, setEditing] = useState(null);
  const [editText, setEditText] = useState('');
  const viewport = useRef(null);
  const gesture = useRef(null);
  const drag = useRef(null);
  const space = useRef(false);
  const bulkRef = useRef(null);
  const typeRef = useRef(null);
  const hand = tool === 'hand';
  const typing = tool === 'type';
  const frames = useMemo(() => {
    let left = 0;
    return doc.pages.map(page => {
      const geo = geometry(page);
      const frame = { id: page.id, left, width: geo.width * 3, height: geo.height * 3 };
      left += frame.width + 100;
      return frame;
    });
  }, [doc.pages]);
  const camera = useCanvasCamera(viewport, frames, Boolean(data));
  const { view, setView } = camera;
  const visible = new Set(camera.visible);
  const selected = useMemo(() => new Set(selection), [selection]);
  const active = doc.pages.find(p => p.id === pages[0]);
  const library = useMemo(() => {
    const entries = new Map(catalog.map(c => [c.char, c]));
    for (const cell of [...doc.library, ...doc.pages.flatMap(p => p.cells)]) {
      if (!entries.has(cell.char)) entries.set(cell.char, { char: cell.char, has_glyph: false, used_in_template: false });
    }
    return [...entries.values()].map(c => ({ ...c, id: `library-${c.char.codePointAt(0)}` }));
  }, [catalog, doc.library, doc.pages]);
  const blocks = useMemo(() => [...library, ...doc.library, ...doc.pages.flatMap(p => p.cells)], [library, doc.library, doc.pages]);
  const placed = useMemo(() => {
    const counts = new Map();
    for (const page of doc.pages) for (const c of page.cells) counts.set(c.char, (counts.get(c.char) || 0) + 1);
    return counts;
  }, [doc.pages]);
  const filteredLibrary = library.filter(block => {
    if (libraryQuery && !block.char.includes(libraryQuery) && !code(block.char).toLowerCase().includes(libraryQuery.toLowerCase())) return false;
    if (placementFilter === 'never' && (block.used_in_template || placed.has(block.char))) return false;
    if (placementFilter === 'current-missing' && placed.has(block.char)) return false;
    if (placementFilter === 'current' && !placed.has(block.char)) return false;
    if (glyphFilter === 'missing' && block.has_glyph) return false;
    if (glyphFilter === 'formal' && !block.has_glyph) return false;
    return true;
  });
  const pageSelection = selection.filter(id => !id.startsWith('library-'));
  const generic = (doc.mode || 'assigned') === 'generic';
  const dirty = useMemo(() => isDirtyDoc(doc, baseline), [doc, baseline]);
  const systemPaper = Boolean(data?.system);
  useEffect(() => { setLibraryLimit(120); }, [libraryQuery, placementFilter, glyphFilter]);
  const count = useMemo(() => doc.pages.reduce((n, p) => n + (doc.mode === 'generic' ? geometry(p).capacity : p.cells.length), 0), [doc.pages, doc.mode]);
  function highlightDrop(element) {
    if (dropTarget.current === element) return;
    dropTarget.current?.classList.remove('drop');
    dropTarget.current = element;
    element?.classList.add('drop');
  }
  useEffect(() => () => { dropTarget.current?.classList.remove('drop'); }, []);

  useEffect(() => {
    let alive = true;
    setData(null);
    Promise.all([getJson(recordId ? `/api/templates?id=${encodeURIComponent(recordId)}` : '/api/templates'), getJson('/api/blocks')]).then(async ([payload, shared]) => {
      if (!alive) return;
      let next = { mode: payload.mode || 'assigned', title: payload.title, library: (payload.editor_library || []).map(char => ({ id: uid(), char })), pages: (payload.editor_pages || []).map(p => ({ ...makePage(p.orientation, p.cell_mm), format: p.paper_format || 'A4', cells: p.cells.map(c => ({ ...c, id: uid() })) })) };
      if (!next.pages.length) next.pages.push(makePage());
      const origin = persistableDoc(next);
      if (!payload.saved && resumeDraft) {
        try {
          const stored = JSON.parse(sessionStorage.getItem(DRAFT));
          if (stored?.pages?.length && stored.pages.length <= 30 && Array.isArray(stored.library)) next = stored;
          else {
            const legacy = JSON.parse(sessionStorage.getItem('handfont-template-draft'));
            if (legacy?.cells) next = { title: legacy.title || next.title, pages: [makePage(legacy.orientation, legacy.size)], library: parseCells(legacy.cells.join('')).map(char => ({ id: uid(), char })) };
          }
        } catch { /* Keep a usable empty document if a draft is unavailable. */ }
      }
      if (!recordId && !resumeDraft && requestedChars) {
        const chars = parseCells(requestedChars);
        next.pages = [];
        for (let i = 0; i < chars.length;) {
          if (next.pages.length >= 30) { next.library.push(...chars.slice(i).map(char => ({ id: uid(), char }))); break; }
          const page = makePage();
          page.cells = chars.slice(i, i + geometry(page).capacity).map((char, slot) => ({ id: uid(), char, slot }));
          next.pages.push(page); i += page.cells.length;
        }
      }
      if (!payload.saved) next.mode = 'assigned';
      if (next.mode === 'generic' && next.pages.length > 1) next.pages = next.pages.slice(0, 1);
      const oldChars = [...new Set([...next.library, ...next.pages.flatMap(p => p.cells)].map(c => c.char))];
      const known = new Set(shared.characters.map(c => c.char));
      const missing = oldChars.filter(c => !known.has(c));
      if (missing.length) shared = await postJson('/blocks/add', { characters: missing.map(code).join(' ') });
      if (!alive) return;
      setCatalog(shared.characters);
      setDoc(next); setPages([next.pages[0].id]); setOpenPages([next.pages[0].id]); setSelection([]); setPast([]); setFuture([]);
      setBaseline(payload.saved ? persistableDoc(next) : origin); setData(payload); setError('');
    }).catch(e => { if (alive) setError(e.message); });
    return () => { alive = false; };
  }, [recordId, resumeDraft, requestedChars]);

  function applyView(update) {
    setView(current => {
      const next = typeof update === 'function' ? update(current) : update;
      if (!generic || !viewport.current || !frames[0]) return next;
      return clampCamera(next, frames[0], viewport.current.clientWidth, viewport.current.clientHeight);
    });
  }
  function focusPage(pageId, nextDoc = doc) {
    const page = nextDoc.pages.find(p => p.id === pageId);
    if (!page || !viewport.current) return;
    const geo = geometry(page), rect = viewport.current.getBoundingClientRect();
    const zoom = clampZoom(Math.min((rect.width - 100) / (geo.width * 3), (rect.height - 180) / (geo.height * 3)));
    const offset = nextDoc.pages.slice(0, nextDoc.pages.indexOf(page)).reduce((sum, p) => sum + geometry(p).width * 3 + 100, 0);
    applyView({ zoom, x: (rect.width - geo.width * 3 * zoom) / 2 - offset * zoom, y: Math.max(50, (rect.height - geo.height * 3 * zoom) / 2 - 20) });
  }
  useEffect(() => { if (data) focusPage(doc.pages[0]?.id); }, [data]);
  useEffect(() => {
    const el = viewport.current;
    if (!el) return;
    let gestureScale = 1;
    const point = e => {
      const rect = el.getBoundingClientRect();
      return { x: e.clientX - rect.left, y: e.clientY - rect.top };
    };
    function wheel(e) {
      if (isPinchWheel(e)) {
        e.preventDefault();
        const { x, y } = point(e);
        applyView(v => zoomCamera(v, Math.exp(-e.deltaY * .008), x, y));
        return;
      }
      if (!el.contains(e.target)) return;
      e.preventDefault();
      applyView(v => ({ ...v, x: v.x - e.deltaX, y: v.y - e.deltaY }));
    }
    function gestureStart(e) { e.preventDefault(); gestureScale = 1; }
    function gestureChange(e) {
      e.preventDefault();
      const factor = e.scale / gestureScale;
      gestureScale = e.scale;
      const { x, y } = point(e);
      applyView(v => zoomCamera(v, factor, x, y));
    }
    function keys(e) {
      if (/INPUT|TEXTAREA|SELECT/.test(e.target.tagName) || e.isComposing || !isBrowserZoomKey(e)) return;
      e.preventDefault();
      if (e.key === '0' || e.code === 'Digit0' || e.code === 'Numpad0') return;
      const shrink = e.key === '-' || e.code === 'Minus' || e.code === 'NumpadSubtract';
      applyView(v => zoomCamera(v, shrink ? 1 / 1.2 : 1.2, el.clientWidth / 2, el.clientHeight / 2));
    }
    function release() { space.current = false; gesture.current = null; setPanning(false); }
    const opts = { passive: false, capture: true };
    window.addEventListener('wheel', wheel, opts);
    window.addEventListener('gesturestart', gestureStart, opts);
    window.addEventListener('gesturechange', gestureChange, opts);
    window.addEventListener('gestureend', gestureStart, opts);
    window.addEventListener('keydown', keys, { capture: true });
    window.addEventListener('blur', release);
    return () => {
      window.removeEventListener('wheel', wheel, opts);
      window.removeEventListener('gesturestart', gestureStart, opts);
      window.removeEventListener('gesturechange', gestureChange, opts);
      window.removeEventListener('gestureend', gestureStart, opts);
      window.removeEventListener('keydown', keys, { capture: true });
      window.removeEventListener('blur', release);
    };
  }, [data, generic, frames, setView]);
  function zoomAt(factor, x = viewport.current.clientWidth / 2, y = viewport.current.clientHeight / 2) {
    applyView(v => zoomCamera(v, factor, x, y));
  }
  function store(next) {
    setDoc(next);
    try { sessionStorage.setItem(DRAFT, JSON.stringify(next)); } catch { setNotice('草稿存储不可用，请及时导出。'); }
  }
  function update(next, picked = selection) {
    if (next.pages.reduce((n, p) => n + p.cells.length, 0) > 1000) { setError('每个模板最多 1000 个字块。'); return false; }
    setPast(stack => [...stack.slice(-29), doc]); setFuture([]); store(next); setSelection(picked); setError(''); return true;
  }
  function undo(redo = false) {
    const stack = redo ? future : past;
    if (!stack.length) return;
    const next = stack.at(-1);
    if (redo) { setFuture(stack.slice(0, -1)); setPast(p => [...p, doc]); }
    else { setPast(stack.slice(0, -1)); setFuture(p => [...p, doc]); }
    store(next); setSelection([]); setPages([next.pages[0].id]); setEditing(null);
  }
  async function add(text) {
    setBusy(true); setError('');
    try {
      const chars = [...new Set(parseCells(text))];
      if (!chars.length) return;
      const next = await postJson('/blocks/add', { characters: chars.map(code).join(' ') });
      setCatalog(next.characters); setSelection(chars.map(c => `library-${c.codePointAt(0)}`));
      setBulk(''); setLibraryQuery(''); setPlacementFilter('all'); setGlyphFilter('all');
      setNotice(`已保存到通用字块库，共 ${next.characters.length} 字。可以反复加入任意模板。`);
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }
  useEffect(() => {
    if (addCharsOpen) bulkRef.current?.focus();
  }, [addCharsOpen]);
  useEffect(() => {
    if (typing) typeRef.current?.focus();
  }, [typing]);
  async function typeIn(text) {
    setBusy(true); setError('');
    try {
      const chars = parseCells(text);
      if (!chars.length) return;
      const shared = await postJson('/blocks/add', { characters: [...new Set(chars)].map(code).join(' ') });
      setCatalog(shared.characters);
      const start = caret || nextEmpty(doc, active?.id || doc.pages[0]?.id, 0) || { pageId: doc.pages[0].id, slot: 0 };
      const placed = placeChars(doc, chars, start.pageId, start.slot);
      if (!update(placed.doc, placed.ids)) return;
      setCaret(placed.caret);
      setTypeText('');
      if (placed.created.length) setOpenPages(current => [...current, ...placed.created.filter(id => !current.includes(id))]);
      const lastPage = placed.doc.pages.find(p => p.cells.some(c => c.id === placed.ids.at(-1)));
      if (lastPage) { setPages([lastPage.id]); focusPage(lastPage.id, placed.doc); }
      setNotice(`已按阅读顺序放入 ${placed.ids.length} 个字，已有字格保持不动。`);
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }
  function move(ids, pageId, slot) {
    try {
      if (update(placeFromLibrary(doc, library, ids, pageId, slot), ids) && pageId) setPages([pageId]);
    } catch (e) { setError(e.message); }
    highlightDrop(null); drag.current = null;
  }
  function pickBlock(block, e, pageId) {
    if (hand || typing || space.current) return;
    e.stopPropagation();
    setSelection(current => e.shiftKey || e.metaKey || e.ctrlKey ? current.includes(block.id) ? current.filter(v => v !== block.id) : [...current, block.id] : [block.id]);
    if (pageId) setPages([pageId]);
  }
  function startDrag(block, e) {
    if (space.current || hand || typing) { e.preventDefault(); return; }
    const ids = selected.has(block.id) ? selection : [block.id];
    setSelection(ids); drag.current = ids;
    e.dataTransfer.effectAllowed = ids.every(id => id.startsWith('library-')) ? 'copy' : 'move'; e.dataTransfer.setData('text/plain', ids.join(','));
  }
  function choosePage(pageId, e) {
    setPages(current => e?.shiftKey || e?.metaKey || e?.ctrlKey ? current.includes(pageId) ? current.filter(v => v !== pageId) : [...current, pageId] : [pageId]);
    setSelection([]);
    setOpenPages(current => current.includes(pageId) ? current : [...current, pageId]);
  }
  function togglePageOpen(pageId, e) {
    e.stopPropagation();
    setOpenPages(current => current.includes(pageId) ? current.filter(id => id !== pageId) : [...current, pageId]);
  }
  function newPage() {
    if (generic) return;
    if (doc.pages.length >= 30) { setError('最多 30 页。'); return; }
    const page = makePage(active?.orientation, active?.size), next = { ...doc, pages: [...doc.pages, page] };
    update(next, []); setPages([page.id]); setOpenPages(current => current.includes(page.id) ? current : [...current, page.id]); focusPage(page.id, next);
  }
  function deletePages(ids = pages) {
    const target = new Set(ids);
    const removed = doc.pages.filter(p => target.has(p.id));
    let remaining = doc.pages.filter(p => !target.has(p.id));
    if (!remaining.length) remaining = [makePage()];
    const next = { ...doc, pages: remaining, library: [...doc.library, ...removed.flatMap(p => p.cells.map(({ id, char }) => ({ id, char })))] };
    update(next, []); setPages([remaining[0].id]); setOpenPages(current => current.filter(id => remaining.some(p => p.id === id) || id === remaining[0].id)); focusPage(remaining[0].id, next);
  }
  function removeBlocks() { if (!pageSelection.length) { setNotice('通用字块请在字符库中管理；这里仅移除模板中的字块。'); return; } update({ ...doc, library: doc.library.filter(c => !selected.has(c.id)), pages: doc.pages.map(p => ({ ...p, cells: p.cells.filter(c => !selected.has(c.id)) })) }, []); }
  function duplicate() {
    if (!active) return;
    const sources = blocks.filter(c => selected.has(c.id));
    const ids = sources.map(c => `library-${c.char.codePointAt(0)}`);
    move(ids, active.id, 0);
  }
  function editBlock() { const block = blocks.find(c => c.id === selection[0]); if (block) { setEditing(block.id); setEditText(block.char); } }
  async function applyEdit() {
    setBusy(true);
    try {
      const chars = parseCells(editText); if (chars.length !== 1) throw new Error('每个字块填写一个字符。');
      const shared = await postJson('/blocks/add', { characters: chars.map(code).join(' ') });
      setCatalog(shared.characters);
      const replace = c => c.id === editing ? { ...c, char: chars[0] } : c;
      update({ ...doc, library: doc.library.map(replace), pages: doc.pages.map(p => ({ ...p, cells: p.cells.map(replace) })) }); setEditing(null);
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  async function persist() {
    if (editing) throw new Error('请先完成字块编辑。');
    const result = await postJson('/template', {
      ...(recordId ? { id: recordId } : {}),
      title: doc.title, mode: generic ? 'generic' : 'assigned',
      editor_library: [],
      editor_pages: (generic ? doc.pages.slice(0, 1) : doc.pages).map(p => ({ paper_format: p.format || 'A4', orientation: p.orientation, cell_mm: p.size, cells: p.cells.map(({ slot, char }) => ({ slot, char })) })),
    });
    sessionStorage.removeItem(DRAFT);
    sessionStorage.removeItem('handfont-template-draft');
    setBaseline(persistableDoc(doc));
    return result;
  }
  async function save() {
    setBusy(true); setBusyKind('save'); setError('');
    try {
      const result = await persist();
      if (!recordId && result.redirect) navigate(result.redirect);
    } catch (e) { setError(e.message); } finally { setBusy(false); setBusyKind(''); }
  }
  async function exportPdf() {
    setBusy(true); setBusyKind('export'); setError('');
    try {
      let name = recordId;
      if (dirty || !name) {
        const result = await persist();
        name = (result.redirect || '').replace(/^\/template\//, '') || name;
        downloadTemplatePdf(name);
        if (!recordId && result.redirect) navigate(result.redirect);
        return;
      }
      downloadTemplatePdf(name);
    } catch (e) { setError(e.message); } finally { setBusy(false); setBusyKind(''); }
  }
  const askLeave = useCallback(() => {
    if (!dirty) navigate('/templates');
    else setLeaveOpen(true);
  }, [dirty, navigate]);
  function confirmLeave() {
    sessionStorage.removeItem(DRAFT);
    sessionStorage.removeItem('handfont-template-draft');
    setLeaveOpen(false);
    navigate('/templates');
  }
  useHeaderBack({ to: '/templates', label: '返回模板库', onClick: askLeave, disabled: busy });
  function shortcuts(e) {
    if (/INPUT|TEXTAREA|SELECT/.test(e.target.tagName) || e.target.closest('.select-menu') || e.nativeEvent.isComposing) return;
    if (e.code === 'Space') { if (generic) return; e.preventDefault(); space.current = true; }
    const mod = e.metaKey || e.ctrlKey;
    if (mod && e.key.toLowerCase() === 'z') { e.preventDefault(); undo(e.shiftKey); }
    if (mod && e.key.toLowerCase() === 'a') { e.preventDefault(); setSelection(active ? active.cells.map(c => c.id) : []); }
    if (mod && e.key.toLowerCase() === 'd' && selection.length) { e.preventDefault(); duplicate(); }
    if ((e.key === 'Delete' || e.key === 'Backspace') && selection.length) { e.preventDefault(); removeBlocks(); }
    if (e.key === 'Escape') {
      if (typing) { setTool('select'); setTypeText(''); return; }
      setSelection([]); setEditing(null);
    }
  }
  const canvasEvents = useRef(null);
  useLayoutEffect(() => {
    canvasEvents.current = { choosePage, pickBlock, move, setEditing, setEditText, startDrag, highlightDrop, selection, space, drag, tool, setCaret: next => { setCaret(next); typeRef.current?.focus(); } };
  });
  if (!data) return <main className="template-loading"><ErrorNote error={error} />正在加载编辑器…
    <ConfirmDialog open={leaveOpen} title="尚未保存" confirmLabel="不保存并离开" danger={false} onConfirm={confirmLeave} onCancel={() => setLeaveOpen(false)}>
      这个模板还没有保存。离开后当前内容不会保留。
    </ConfirmDialog>
  </main>;
  return <main className="template-editor">
    <fieldset disabled={busy} className={`studio${generic ? ' is-paper' : ''}`} onKeyDown={shortcuts} onKeyUp={e => { if (e.code === 'Space') space.current = false; }}>
      <aside className="studio-left">
        <section className="studio-document">
          <label htmlFor="template-title">模版名称</label>
          <input id="template-title" value={doc.title} maxLength={80} disabled={systemPaper} onChange={e => store({ ...doc, title: e.target.value })} />
          {generic && active ? <div className="studio-page-edit">
            <label htmlFor="page-format">页面大小<SelectMenu id="page-format" ariaLabel="页面大小" value={active.format || 'A4'} onChange={format => update(resizePages(doc, doc.pages.map(p => p.id), { format }))} options={['A5', 'A4', 'A3'].map(format => ({ value: format, label: format }))} /></label>
            <label htmlFor="page-orientation">页面方向<SelectMenu id="page-orientation" ariaLabel="页面方向" value={active.orientation} onChange={orientation => update(resizePages(doc, doc.pages.map(p => p.id), { orientation }))} options={[{ value: 'portrait', label: '纵向' }, { value: 'landscape', label: '横向' }]} /></label>
            <label htmlFor="page-cell">字格大小<SelectMenu id="page-cell" ariaLabel="字格大小" value={String(active.size)} onChange={size => update(resizePages(doc, doc.pages.map(p => p.id), { size: Number(size) }))} options={[10, 12, 14, 16, 18, 20].map(size => ({ value: String(size), label: `${size} mm` }))} /></label>
          </div> : null}
        </section>
        {generic ? null : <section className="studio-layers">
          <div className="studio-section-title"><strong>页面</strong><button type="button" className="with-icon" onClick={newPage} aria-label="新增页面" title="新增页面"><PlusIcon {...iconSm} /></button></div>
          {active ? <div className="studio-page-edit">
            <label htmlFor="page-format">页面大小<SelectMenu id="page-format" ariaLabel="页面大小" value={pages.some(id => (doc.pages.find(p => p.id === id)?.format || 'A4') !== (active.format || 'A4')) ? '' : active.format || 'A4'} placeholder="混合大小" onChange={format => { update(resizePages(doc, pages, { format })); setNotice('已更新页面大小，超出容量的字块已退回库。'); }} options={['A5', 'A4', 'A3'].map(format => ({ value: format, label: format }))} /></label>
            <label htmlFor="page-orientation">页面方向<SelectMenu id="page-orientation" ariaLabel="页面方向" value={pages.some(id => doc.pages.find(p => p.id === id)?.orientation !== active.orientation) ? '' : active.orientation} placeholder="混合方向" onChange={orientation => { update(resizePages(doc, pages, { orientation })); setNotice('已更新选中页面，超出容量的字块已退回库。'); }} options={[{ value: 'portrait', label: '纵向' }, { value: 'landscape', label: '横向' }]} /></label>
            <label htmlFor="page-cell">字格大小<SelectMenu id="page-cell" ariaLabel="字格大小" value={pages.some(id => doc.pages.find(p => p.id === id)?.size !== active.size) ? '' : String(active.size)} placeholder="混合尺寸" onChange={size => { update(resizePages(doc, pages, { size: Number(size) })); setNotice('已更新字格大小，超出容量的字块已退回库。'); }} options={[10, 12, 14, 16, 18, 20].map(size => ({ value: String(size), label: `${size} mm` }))} /></label>
          </div> : null}
          <div className="studio-section-title"><strong>图层</strong></div>
          {doc.pages.map((page, index) => {
            const open = openPages.includes(page.id);
            const on = pages.includes(page.id);
            return <div className={`studio-layer${on ? ' is-current' : ''}${open ? ' is-open' : ''}`} key={page.id}>
              <div className="studio-page-row">
                <button type="button" className="studio-page-hit" aria-pressed={on} onClick={e => { choosePage(page.id, e); focusPage(page.id); }}>
                  页面 {String(index + 1).padStart(2, '0')}
                </button>
                <button type="button" className="danger with-icon studio-page-remove" disabled={busy} aria-label={`移除页面 ${index + 1}`} title="移除页面" onClick={e => { e.stopPropagation(); deletePages([page.id]); }}><TrashIcon {...iconSm} /></button>
                <button type="button" className="studio-page-toggle" aria-expanded={open} aria-label={open ? '折叠图层' : '展开图层'} onClick={e => togglePageOpen(page.id, e)}>{open ? <ChevronDownIcon {...iconSm} /> : <ChevronRightIcon {...iconSm} />}</button>
              </div>
              {open ? <div className="studio-child-layers">{page.cells.slice().sort((a, b) => a.slot - b.slot).map(c => <button type="button" className={selected.has(c.id) ? 'is-current' : ''} key={c.id} onClick={e => pickBlock(c, e, page.id)}><GridIcon {...iconSm} size={14} />{c.char}</button>)}</div> : null}
            </div>;
          })}
        </section>}
        <div className="studio-document-actions">
          <div className="studio-document-actions-row">
            {recordId
              ? <button type="button" className="with-icon" onClick={save} disabled={!count || busy || !dirty}><FloppyDiskIcon {...iconSm} />{busyKind === 'save' ? '正在更新…' : '更新'}</button>
              : <button type="button" className="with-icon" onClick={save} disabled={!count || busy || !dirty}><FloppyDiskIcon {...iconSm} />{busyKind === 'save' ? '正在保存…' : '保存'}</button>}
            <button type="button" className="with-icon" onClick={exportPdf} disabled={!count || busy}><DownloadIcon {...iconSm} />{busyKind === 'export' ? '正在导出…' : '导出'}</button>
          </div>
        </div>
      </aside>
      <div ref={viewport} className={`studio-viewport${generic || hand ? ' hand' : ''}${panning ? ' panning' : ''}${typing ? ' type' : ''}`} tabIndex={0} aria-label={generic ? '页面预览' : '无限画布'}
        onPointerDown={e => {
          if (busy || (e.button !== 0 && e.button !== 1)) return;
          const pan = generic || hand || space.current || e.button === 1 || e.target === e.currentTarget;
          if (!pan) return;
          e.preventDefault(); e.currentTarget.focus(); gesture.current = { x: e.clientX, y: e.clientY, view: view.current }; e.currentTarget.setPointerCapture(e.pointerId); setPanning(true);
          if (!generic && !hand && !space.current && e.button === 0) setSelection([]);
        }}
        onPointerMove={e => { if (gesture.current) { const g = gesture.current; applyView({ ...g.view, x: g.view.x + e.clientX-g.x, y: g.view.y + e.clientY-g.y }); } }}
        onPointerUp={() => { gesture.current = null; setPanning(false); }} onPointerCancel={() => { gesture.current = null; setPanning(false); }} onLostPointerCapture={() => { gesture.current = null; setPanning(false); }}
        onCopy={e => { if (!selection.length) return; e.preventDefault(); e.clipboardData.setData('text/plain', blocks.filter(c => selected.has(c.id)).map(c => c.char).join('')); }}
        onPaste={e => { if (/INPUT|TEXTAREA/.test(e.target.tagName)) return; e.preventDefault(); const text = e.clipboardData.getData('text/plain'); if (typing) typeIn(text); else add(text); }}
        >
        <div ref={camera.world} className="studio-world">
          {doc.pages.map((page, pageIndex) => {
            // Keep a native drag source mounted even if the camera leaves its page.
            if (generic && pageIndex > 0) return null;
            if (!visible.has(page.id) && !page.cells.some(c => drag.current?.includes(c.id))) return null;
            return <CanvasFrame key={page.id} page={page} pageIndex={pageIndex} left={frames[pageIndex].left}
              generic={generic} selectedPage={pages.includes(page.id)} guides={guides} selected={selected} hand={hand} typing={typing} caret={caret} events={canvasEvents} />;
          })}
        </div>
      </div>
      {generic ? null : <aside className="studio-right">
        <section className="studio-library" onDragOver={e => { if (drag.current) { e.preventDefault(); highlightDrop(e.currentTarget); } }} onDrop={e => { e.preventDefault(); if (drag.current) move(drag.current,null); }}>
          <div className="studio-section-title"><strong>通用字块库</strong><span>{library.length}</span></div>
          <button type="button" className="studio-add with-icon" aria-expanded={addCharsOpen} onClick={() => setAddCharsOpen(open => !open)}><PlusIcon {...iconSm} />加入字符</button>
          {addCharsOpen ? <div className="studio-library-add">
            <textarea ref={bulkRef} aria-label="输入文字到字块库" rows={3} value={bulk} onChange={e => setBulk(e.target.value)} placeholder="输入文字或 U+5B57…" />
            <button type="button" className="studio-add with-icon" disabled={!bulk.trim()} onClick={() => add(bulk)}><PlusIcon {...iconSm} />加入字块库</button>
            <Disclosure summary="字表与导入">
              <div className="studio-presets"><button type="button" className="chip" onClick={() => add(parseCells(data.preset).filter(c => /[\u4e00-\u9fff]/u.test(c)).join(''))}>常用中文</button><button type="button" className="chip" onClick={() => add('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789')}>英文数字</button><label className="icon-button file-label" aria-label="导入 TXT" title="导入 TXT"><FileIcon {...iconSm} /><input type="file" accept=".txt,text/plain" onChange={async e => { const file = e.target.files?.[0]; e.target.value=''; if (!file) return; try { if (file.size > 100000) throw new Error('字表文件过大，请分批。'); add(await file.text()); } catch (e) { setError(e.message); } }} /></label></div>
            </Disclosure>
          </div> : null}
          <div className="studio-library-filters">
            <label htmlFor="library-query">搜索字符<input id="library-query" value={libraryQuery} onChange={e => { setLibraryQuery(e.target.value); setSelection([]); }} placeholder="字符或 U+5B57" /></label>
            <label htmlFor="library-placement">模板使用<SelectMenu id="library-placement" ariaLabel="模板使用" value={placementFilter} onChange={value => { setPlacementFilter(value); setSelection([]); }} options={[{ value: 'all', label: '全部字块' }, { value: 'never', label: '未加入过模板' }, { value: 'current-missing', label: '未加入当前模板' }, { value: 'current', label: '已加入当前模板' }]} /></label>
            <label htmlFor="library-glyph">正式字形<SelectMenu id="library-glyph" ariaLabel="正式字形" value={glyphFilter} onChange={value => { setGlyphFilter(value); setSelection([]); }} options={[{ value: 'all', label: '全部' }, { value: 'missing', label: '暂无正式字形' }, { value: 'formal', label: '已有正式字形' }]} /></label>
          </div>
          <div className="studio-library-actions">
            <button type="button" className="chip with-icon" disabled={!filteredLibrary.length} onClick={() => setSelection(filteredLibrary.map(c => c.id))} aria-label={`选择筛选结果 · ${filteredLibrary.length}`}><CheckIcon {...iconSm} />选择 · {filteredLibrary.length}</button>
            <button type="button" className="chip with-icon" disabled={!selection.length || !active} onClick={() => move(selection,active.id,0)} aria-label="加入当前页（可重复）"><GridIcon {...iconSm} />加入当前页</button>
          </div>
          <div className="studio-blocks">{filteredLibrary.slice(0, libraryLimit).map(block => <button key={block.id} className={selected.has(block.id) ? 'selected' : ''} aria-pressed={selected.has(block.id)} draggable={!hand && !typing} onClick={e => pickBlock(block,e)} onDragStart={e => startDrag(block,e)} onDragEnd={() => { drag.current=null; highlightDrop(null); }} onDoubleClick={() => active && move([block.id], active.id, 0)} title={`${code(block.char)} · 当前模板 ${placed.get(block.char) || 0} 次 · ${block.has_glyph ? '已有正式字形' : '暂无正式字形'}`}><strong className={block.has_glyph ? '' : 'library-placeholder'}>{block.char}</strong><small>{placed.has(block.char) ? `已加入 ${placed.get(block.char)} 次` : block.used_in_template ? '曾加入模板' : '未加入模板'}</small></button>)}</div>
          {filteredLibrary.length > libraryLimit && <button className="chip" onClick={() => setLibraryLimit(n => n + 120)}>显示更多 · 还有 {filteredLibrary.length - libraryLimit} 字</button>}
          {!filteredLibrary.length && <p className="studio-library-empty">{library.length ? '没有符合筛选条件的字块' : '添加字符后，所有模板都可以使用'}</p>}
        </section>
      </aside>}
      <div className="studio-bottom">
        {typing ? <form className="studio-type" onSubmit={e => { e.preventDefault(); typeIn(typeText); }}>
          <label htmlFor="studio-type-input">{caret && doc.pages.some(p => p.id === caret.pageId) ? `从页面 ${String(doc.pages.findIndex(p => p.id === caret.pageId) + 1).padStart(2, '0')} · 第 ${caret.slot + 1} 格起，按阅读顺序填入空格` : '点击字格选择起点，或从当前页第一个空格开始'}</label>
          <textarea id="studio-type-input" ref={typeRef} rows={2} value={typeText} maxLength={20000} placeholder="输入或粘贴一段文字，例如：春风又绿江南岸" onChange={e => setTypeText(e.target.value)} onKeyDown={e => { if (e.nativeEvent.isComposing || e.keyCode === 229) return; if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); typeIn(typeText); } }} />
          <div className="studio-type-actions">
            <button type="submit" className="with-icon" disabled={busy || !typeText.trim()}><KeyboardIcon {...iconSm} />放入模板</button>
            <label className="with-icon file-label studio-type-import" aria-label="导入 TXT">
              <FileIcon {...iconSm} />导入
              <input type="file" accept=".txt,.csv,.tsv,text/plain,text/csv" onChange={async e => { const file = e.target.files?.[0]; e.target.value = ''; if (!file) return; try { if (file.size > 100000) throw new Error('字表文件过大，请分批。'); let text = await file.text(); if (/\.(csv|tsv)$/i.test(file.name || '')) text = text.replace(/[,\t]/g, '\n'); await typeIn(text); } catch (err) { setError(err.message); } }} />
            </label>
          </div>
        </form> : null}
        <div className="studio-tool-row">
        <div className="studio-tools" aria-label={generic ? '预览工具' : '编辑工具'}>
        {generic ? null : <>
        <button className={tool === 'select' ? 'selected' : ''} aria-pressed={tool === 'select'} aria-label="选择" title="选择" onClick={() => setTool('select')}><CursorIcon {...iconSm} /></button>
        <button className={hand ? 'selected' : ''} aria-pressed={hand} aria-label="抓手" title="抓手" onClick={() => setTool('hand')}><HandIcon {...iconSm} /></button>
        <button className={typing ? 'selected' : ''} aria-pressed={typing} aria-label="打字" title="打字放入" onClick={() => { setTool('type'); setSelection([]); setCaret(current => current || nextEmpty(doc, active?.id || doc.pages[0].id, 0)); }}><KeyboardIcon {...iconSm} /></button>
        <span className="studio-divider" />
        </>}
        <button title="撤销 · Ctrl/⌘ Z" aria-label="撤销" disabled={!past.length} onClick={() => undo()}><UndoIcon {...iconSm} /></button>
        <button title="重做" aria-label="重做" disabled={!future.length} onClick={() => undo(true)}><RedoIcon {...iconSm} /></button>
        {generic ? null : <>
        <span className="studio-divider" />
        <button aria-label="编辑" title="编辑" disabled={selection.length !== 1 || !pageSelection.length} onClick={editBlock}><PencilIcon {...iconSm} /></button>
        <button aria-label="复制" title="复制" disabled={!selection.length} onClick={duplicate}><DuplicateIcon {...iconSm} /></button>
        <button aria-label="移出模板" title="移出模板，通用库保留" disabled={!pageSelection.length} onClick={() => move(selection,null)}><FolderIcon {...iconSm} /></button>
        <button aria-label="删除" title="删除模板中的字块" disabled={!pageSelection.length} onClick={removeBlocks}><TrashIcon {...iconSm} /></button>
        </>}
        <button aria-label="辅助线" title="辅助线" aria-pressed={guides} className={guides ? 'selected' : ''} onClick={() => setGuides(v => !v)}><RulerIcon {...iconSm} /></button>
      </div><div className="studio-view-tools"><button ref={camera.zoomOut} aria-label="缩小" title="缩小" onClick={() => zoomAt(1/1.2)}><ZoomOutIcon {...iconSm} /></button><span ref={camera.zoomLabel} /><button ref={camera.zoomIn} aria-label="放大" title="放大" onClick={() => zoomAt(1.2)}><ZoomInIcon {...iconSm} /></button><button aria-label="定位页面" title="定位页面" onClick={() => focusPage(active?.id || doc.pages[0].id)}><TargetIcon {...iconSm} /></button></div>
        </div>
      </div>
      {error || notice ? <div className="studio-message"><ErrorNote error={error} />{!error ? <p role="status">{notice}</p> : null}<button className="chip icon-chip" aria-label="关闭提示" title="关闭提示" onClick={() => { setError(''); setNotice(''); }}><CloseIcon {...iconSm} /></button></div> : null}
      {editing ? <div className="studio-edit" role="dialog" aria-label="编辑字块"><label>字符<input autoFocus value={editText} onChange={e => setEditText(e.target.value)} onKeyDown={e => { if (e.nativeEvent.isComposing) return; if (e.key === 'Enter') applyEdit(); if (e.key === 'Escape') setEditing(null); }} /></label><button className="with-icon" onClick={applyEdit}><CheckIcon {...iconSm} />应用</button><button className="secondary with-icon" onClick={() => setEditing(null)}><CloseIcon {...iconSm} />取消</button></div> : null}
    </fieldset>
    <ConfirmDialog open={leaveOpen} title="尚未保存" confirmLabel="不保存并离开" danger={false} onConfirm={confirmLeave} onCancel={() => setLeaveOpen(false)}>
      {recordId ? '当前修改还没有更新到已保存的模板。离开后这些修改不会保留。' : '这个模板还没有保存。离开后当前内容不会保留。'}
    </ConfirmDialog>
  </main>;
}
