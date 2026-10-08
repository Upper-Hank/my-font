import { useRef, useState } from 'react';
import TrashIcon from '@uplus-icon/react/icons/trash';
import { iconSm } from '../ui.jsx';

const rectBetween = (a, b) => [Math.min(a[0], b[0]), Math.min(a[1], b[1]), Math.abs(a[0] - b[0]), Math.abs(a[1] - b[1])];
export default function SourceRegions({ page, onChange, disabled, returnChar }) {
  const [selected, setSelected] = useState(null);
  const [drawing, setDrawing] = useState(false);
  const [draft, setDraft] = useState(null);
  const drag = useRef(null);
  const region = page.regions.find(r => r.id === selected);
  const update = (id, patch) => onChange(page.regions.map(r => r.id === id ? { ...r, ...patch } : r));
  function point(event) {
    const box = event.currentTarget.getBoundingClientRect();
    return [Math.max(0, Math.min(page.width, (event.clientX - box.left) / box.width * page.width)), Math.max(0, Math.min(page.height, (event.clientY - box.top) / box.height * page.height))];
  }
  function start(event) {
    if (disabled || !drawing || event.button !== 0) return;
    const origin = point(event);
    drag.current = origin;
    event.currentTarget.setPointerCapture(event.pointerId);
    setDraft([...origin, 0, 0]);
  }
  function finish(event) {
    if (!drag.current) return;
    const rect = rectBetween(drag.current, point(event));
    drag.current = null; setDraft(null);
    if (rect[2] < 2 || rect[3] < 2) return;
    addRegion(rect);
  }
  function addRegion(rect) {
    const id = crypto.randomUUID();
    onChange([...page.regions, { id, rect, char: page.regions.length === 0 ? returnChar || '' : '' }]);
    setSelected(id); setDrawing(false);
  }
  const position = rect => ({ left: `${rect[0] / page.width * 100}%`, top: `${rect[1] / page.height * 100}%`, width: `${rect[2] / page.width * 100}%`, height: `${rect[3] / page.height * 100}%` });
  function changeRect(index, percent) {
    if (!Number.isFinite(percent)) return;
    const next = [...region.rect];
    next[index] = percent / 100 * (index % 2 === 0 ? page.width : page.height);
    next[0] = Math.max(0, Math.min(page.width - 2, next[0]));
    next[1] = Math.max(0, Math.min(page.height - 2, next[1]));
    next[2] = Math.max(2, Math.min(page.width - next[0], next[2]));
    next[3] = Math.max(2, Math.min(page.height - next[1], next[3]));
    update(selected, { rect: next });
  }
  return <div className="source-region-layout">
    <div className={`source-image${drawing ? ' is-drawing' : ''}`} onPointerDown={start} onPointerMove={event => { if (drag.current) setDraft(rectBetween(drag.current, point(event))); }} onPointerUp={finish} onPointerCancel={() => { drag.current = null; setDraft(null); }}>
      <img src={page.scan_url} alt={`${page.source_name}取字工作面`} draggable={false} />
      {page.regions.map((r, index) => <button type="button" disabled={disabled || drawing} key={r.id} className={`source-region${selected === r.id ? ' selected' : ''}`} style={position(r.rect)} aria-label={`选择第 ${index + 1} 个取字区域${r.char ? `，${r.char}` : ''}`} aria-pressed={selected === r.id} onClick={() => setSelected(r.id)}><span>{index + 1}{r.char ? ` ${r.char}` : ''}</span></button>)}
      {draft && <div className="source-region source-region-draft" style={position(draft)} />}
    </div>
    <section className="source-region-controls">
      <div className="actions"><button type="button" disabled={disabled || page.regions.length >= 1000} aria-pressed={drawing} onClick={() => setDrawing(value => !value)}>{drawing ? '取消框选' : '框选新字'}</button><button type="button" disabled={disabled || page.regions.length >= 1000} onClick={() => addRegion([page.width * .4, page.height * .4, page.width * .2, page.height * .2])}>添加区域</button></div>
      <p className="hint">{drawing ? '在照片上拖动，框住一个完整字形，留出少量空白。' : '选择照片上的区域，修改对应字符和取字范围。每个区域提取一个完整字形。'}</p>
      <p>{page.regions.length} 个取字区域</p>
      {region && !drawing && <fieldset disabled={disabled}>
        <label>对应字符<input value={region.char} onChange={event => update(selected, { char: event.target.value })} placeholder="可在提取后填写" /></label>
        <div className="source-region-coordinates">{['左侧位置', '顶部位置', '宽度', '高度'].map((label, index) => <label key={label}>{label} %<input type="number" min="0" max="100" step="0.1" value={Number((region.rect[index] / (index % 2 === 0 ? page.width : page.height) * 100).toFixed(2))} onChange={event => changeRect(index, event.target.valueAsNumber)} /></label>)}</div>
        <button type="button" className="danger with-icon" onClick={() => { onChange(page.regions.filter(r => r.id !== selected)); setSelected(null); }}><TrashIcon {...iconSm} />删除区域</button>
      </fieldset>}
      {page.presets?.length > 0 && <button type="button" disabled={disabled} onClick={() => { onChange(page.presets.map(r => ({ ...r, rect: [...r.rect] }))); setSelected(null); setDrawing(false); }}>恢复模板预设</button>}
    </section>
  </div>;
}
