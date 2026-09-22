import { useEffect, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import PencilIcon from '@uplus-icon/react/icons/pencil';
import CursorIcon from '@uplus-icon/react/icons/cursor';
import CheckIcon from '@uplus-icon/react/icons/check';
import UndoIcon from '@uplus-icon/react/icons/undo';
import DuplicateIcon from '@uplus-icon/react/icons/duplicate';
import CloseIcon from '@uplus-icon/react/icons/close';
import RulerIcon from '@uplus-icon/react/icons/ruler';
import { getJson, postJson } from '../api.js';
import { useHeaderBack } from '../components/HeaderBack.jsx';
import { useToast } from '../components/Toast.jsx';
import { ConfirmDialog, Disclosure, ErrorNote, Page, iconSm } from '../ui.jsx';

export default function Strokes() {
  const { run, sample } = useParams();
  const identifier = `${run}/${sample}`;
  const [data, setData] = useState(null);
  const [picked, setPicked] = useState([]);
  const [tool, setTool] = useState('select');
  const [brush, setBrush] = useState(5);
  const [trace, setTrace] = useState([]);
  const [original, setOriginal] = useState(true);
  const [monochrome, setMonochrome] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [regenerate, setRegenerate] = useState(false);
  const [properties, setProperties] = useState(null);
  const [published, setPublished] = useState(false);
  const surface = useRef(null);
  const gesture = useRef(null);
  const strokes = data?.strokes || [];
  const selected = strokes.filter(s => picked.includes(s.id));
  const current = selected.length === 1 ? selected[0] : null;
  const kept = strokes.filter(s => s.visible);
  const unreviewed = kept.filter(s => s.review).length;
  const back = data ? `/results?char=${encodeURIComponent(data.char)}` : '/results';
  const toast = useToast();
  useHeaderBack({ to: `/glyph/${encodeURIComponent(run)}/${encodeURIComponent(sample)}`, label: '返回字形编辑', disabled: busy });
  useEffect(() => {
    let active = true;
    getJson(`/api/strokes?sample=${encodeURIComponent(identifier)}`).then(value => { if (active) setData(value); }).catch(e => { if (active) setError(e.message); });
    return () => { active = false; };
  }, [identifier]);
  useEffect(() => {
    setProperties(current ? { name: current.name, group: current.group, ...current.transform } : null);
  }, [current]);
  async function request(path, extra = {}) {
    setBusy(true); setError('');
    try {
      const value = await postJson(path, { sample: identifier, revision: data.revision, ...extra });
      if (path.endsWith('/publish')) { setPublished(true); toast('已生成一个新字形，原稿和默认选择均保留。', { to: back, action: '查看全部字形' }); }
      else {
        setData(value); setPublished(false); setRegenerate(false);
        setPicked(previous => previous.filter(id => value.strokes.some(s => s.id === id)));
        if (path.endsWith('/generate')) toast('已生成拆分候选。');
      }
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }
  const edit = (operation, args = {}) => request('/strokes/edit', { operation, args: { ids: picked, ...args } });
  function point(e) {
    const rect = surface.current.getBoundingClientRect();
    return [Math.max(0,Math.min(256,(e.clientX-rect.left)/rect.width*256)),Math.max(0,Math.min(256,(e.clientY-rect.top)/rect.height*256))];
  }
  function start(e) {
    if (busy || tool==='select') return;
    if (!current) { setError('请先在右侧选择一个笔画。'); return; }
    if (e.button!==0) return;
    e.preventDefault(); e.currentTarget.setPointerCapture(e.pointerId);
    gesture.current = [point(e)]; setTrace(gesture.current);
  }
  function move(e) {
    if (!gesture.current) return;
    const next = point(e);
    if (tool==='split') gesture.current = [gesture.current[0],next];
    else if (gesture.current.length<2047) gesture.current.push(next);
    setTrace([...gesture.current]);
  }
  function finish(e) {
    if (!gesture.current) return;
    const points = tool==='split' ? [gesture.current[0],point(e)] : [...gesture.current,point(e)];
    gesture.current=null; setTrace([]);
    edit(tool,{ points, brush, overlap:1 });
  }
  if (!data) return <Page><ErrorNote error={error} /><p className="muted">{error ? '无法加载笔画工作区。' : '正在加载笔画工作区…'}</p></Page>;
  return <Page>
    <div className="action-bar"><div><h1>{data.char} · 笔画与部件</h1><p className="hint">原稿保留，拆分结果需要确认。画布操作自动保存，属性需点击应用，最后合成为新的字形。</p></div><div className="actions"><button className="secondary with-icon" disabled={busy} onClick={() => data.revision ? setRegenerate(true) : request('/strokes/generate')}><DuplicateIcon {...iconSm} />{strokes.length ? '重新生成候选' : '生成拆分候选'}</button><button className="with-icon" disabled={busy || !kept.length || unreviewed>0 || published} onClick={() => request('/strokes/publish')}><CheckIcon {...iconSm} />{published ? '已生成新字形' : '合成为新字形'}</button></div></div>
    <ConfirmDialog open={regenerate} title="重新生成笔画候选？" confirmLabel="重新生成" danger={false} busy={busy} onConfirm={() => request('/strokes/generate')} onCancel={() => setRegenerate(false)}>会替换当前拆分草稿和撤销记录，原字形与已生成的新字形不受影响。</ConfirmDialog>
    <ErrorNote error={error} />
    <div className="stroke-status"><span>{data.method === 'connected-ink' ? '独立墨迹候选' : '结构参考＋几何辅助'}</span><span>{data.has_reference ? '有标准笔画参考' : '无标准笔画参考'}</span><span>{strokes.length} 个候选 · {unreviewed} 个待确认{data.expected_count ? ` · 参考 ${data.expected_count} 笔` : ''}</span></div>
    <p className="hint">当前为 256 × 256 栅格拆分，合成会重新描边；细小边缘可能变化，请对照原稿检查。</p>
    <div className="stroke-workspace">
      <section>
        <div className="actions stroke-tools">{[['select','选择',CursorIcon],['split','切分',RulerIcon],['paint','补画',PencilIcon],['erase','擦除',CloseIcon]].map(([key,label,Icon]) => <button key={key} className={`secondary with-icon ${tool===key ? 'is-active' : ''}`} aria-pressed={tool===key} disabled={busy} onClick={() => { gesture.current = null; setTool(key); setTrace([]); }}><Icon {...iconSm} />{label}</button>)}<button className="text-button with-icon" disabled={busy || !data.can_undo} onClick={() => edit('undo')}><UndoIcon {...iconSm} />撤销</button></div>
        <p className="hint">{tool==='split' ? '选择一个候选后，在字形上拖出切分线。切口保留少量重叠，可用补画恢复交叉笔画。' : tool==='paint' || tool==='erase' ? '选择一个笔画，在画布上绘制；可用撤销恢复。' : '从右侧选择笔画，可独立调整位置、大小或组织成部件。'}</p>
        {(tool==='paint'||tool==='erase') && <label>画笔粗细 · {brush}<input type="range" min="1" max="30" value={brush} onChange={e => setBrush(Number(e.target.value))} /></label>}
        <div className={`stroke-surface ${tool!=='select' ? 'drawing' : ''}`} ref={surface} onPointerDown={start} onPointerMove={move} onPointerUp={finish} onPointerCancel={() => { gesture.current=null;setTrace([]); }} onLostPointerCapture={() => { gesture.current=null;setTrace([]); }}>
          {original && <img src={data.original} alt="原始字形对照" className="stroke-original" draggable={false} />}
          {strokes.filter(s => s.visible).map(s => <img key={s.id} src={s.image} alt="" draggable={false} className={monochrome ? 'stroke-layer monochrome' : 'stroke-layer'} style={{ opacity:picked.length && !picked.includes(s.id) ? .2 : .9,transform:`translate(${s.transform.x/256*100}%,${s.transform.y/256*100}%) scale(${s.transform.scale})` }} />)}
          {trace.length>0 && <svg viewBox="0 0 256 256" className="stroke-gesture" aria-hidden="true"><polyline points={trace.map(p => p.join(',')).join(' ')} fill="none" stroke="#d34141" strokeWidth={tool==='split' ? 1 : brush} strokeLinecap="round" /></svg>}
        </div>
        <div className="actions stroke-view-options"><label className="review-choice"><input type="checkbox" checked={original} onChange={e => setOriginal(e.target.checked)} />原稿对照</label><label className="review-choice"><input type="checkbox" checked={monochrome} onChange={e => setMonochrome(e.target.checked)} />黑白合成</label></div>
        {data.notes?.length>0 && <Disclosure className="stroke-notes" summary="拆分说明与待检查项">{data.notes.map((text,index) => <p className="hint" key={index}>{text}</p>)}</Disclosure>}
      </section>
      <aside className="stroke-sidebar">
        <div className="actions"><button className="text-button" disabled={busy || !strokes.length} onClick={() => setPicked(strokes.map(s => s.id))}>全选</button><button className="text-button" disabled={busy || !picked.length} onClick={() => setPicked([])}>取消选择</button><button className="secondary with-icon" disabled={busy || picked.length<2} onClick={() => edit('merge')}><DuplicateIcon {...iconSm} />合并所选</button></div>
        <div className="stroke-list">{strokes.map(s => <label className={`stroke-row ${picked.includes(s.id) ? 'selected' : ''}`} key={s.id}><input type="checkbox" disabled={busy} checked={picked.includes(s.id)} onChange={e => setPicked(previous => e.target.checked ? [...previous,s.id] : previous.filter(id => id!==s.id))} /><img src={s.image} alt="" /><span><strong>{s.name}</strong><small>{s.group ? `${s.group} · ` : ''}{s.visible ? s.review ? '待确认' : '已确认' : '不参与合成'}</small></span></label>)}</div>
        {!strokes.length && <p className="hint">先生成拆分候选，再选择笔画进行检查。</p>}
        {properties && current && <form className="stroke-properties" onSubmit={e => { e.preventDefault(); edit('update',{ patch:{ name:properties.name,group:properties.group,transform:{ x:Number(properties.x),y:Number(properties.y),scale:Number(properties.scale) },review:true } }); }}>
          <label>笔画名称<input value={properties.name} maxLength={40} onChange={e => setProperties(p => ({ ...p,name:e.target.value }))} /></label>
          <label>所属部件<input value={properties.group} maxLength={40} placeholder="例如：木、氵" onChange={e => setProperties(p => ({ ...p,group:e.target.value }))} /></label>
          <label>水平位移<input type="number" min="-128" max="128" required value={properties.x} onChange={e => setProperties(p => ({ ...p,x:e.target.value }))} /></label>
          <label>垂直位移<input type="number" min="-128" max="128" required value={properties.y} onChange={e => setProperties(p => ({ ...p,y:e.target.value }))} /></label>
          <label>缩放倍数<input type="number" min="0.25" max="3" step="0.05" required value={properties.scale} onChange={e => setProperties(p => ({ ...p,scale:e.target.value }))} /></label>
          <button disabled={busy}>应用属性</button>
        </form>}
        {picked.length>0 && <div className="actions stroke-confirm"><button className="with-icon" disabled={busy} onClick={() => edit('update',{patch:{review:false}})}><CheckIcon {...iconSm} />确认所选 · {picked.length}</button><button className="secondary" disabled={busy} onClick={() => edit('update',{patch:{visible:!selected.every(s => s.visible)}})}>{selected.every(s => s.visible) ? '移出合成' : '加入合成'}</button></div>}
      </aside>
    </div>
  </Page>;
}
