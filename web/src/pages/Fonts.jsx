import { AdjustmentFields, ORIGINAL, adjustmentPreview } from '../components/GlyphAdjustment.jsx';
import ManageToolbar from '../components/ManageToolbar.jsx';
import TrashIcon from '@uplus-icon/react/icons/trash';
import PlusIcon from '@uplus-icon/react/icons/plus';
import FileIcon from '@uplus-icon/react/icons/file';
import CameraIcon from '@uplus-icon/react/icons/camera';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { getJson, postJson } from '../api.js';
import { LiveFontTools, useFontLive } from '../components/FontLive.jsx';
import { useToast } from '../components/Toast.jsx';
import { ConfirmDialog, Dialog, ErrorNote, Page, iconSm } from '../ui.jsx';
import { parseCells } from '../lib/template-editor.js';
import SelectMenu from '../SelectMenu.jsx';

const STATUS = { blank: '空白', edge: '触边，需检查' };
const templateUrl = chars => `/template/new?chars=${encodeURIComponent(chars.map(c => `U+${c.codePointAt(0).toString(16)}`).join(" "))}`;

export default function Fonts() {
  const [params, setParams] = useSearchParams();
  const activeChar = params.get('char');
  const { data, setData, exportError } = useFontLive();
  const toast = useToast();
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState('all');
  const [batch, setBatch] = useState('');
  const trash = params.get('view') === 'trash';
  const [view, setView] = useState('vector');
  const [picked, setPicked] = useState([]);
  const [selected, setSelected] = useState([]);
  const [managing, setManaging] = useState(false);
  const [adjusting, setAdjusting] = useState(false);
  const [options, setOptions] = useState({ ...ORIGINAL });
  const library = !activeChar && !trash;
  const enterManage = useCallback(() => { setPicked([]); setSelected([]); setManaging(true); }, []);
  const leaveManage = useCallback(() => { setPicked([]); setSelected([]); setManaging(false); }, []);
  useEffect(() => { setManaging(false); setPicked([]); setSelected([]); setAdjusting(false); }, [activeChar, trash]);
  const [adding, setAdding] = useState(false);
  const [input, setInput] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [deletion, setDeletion] = useState(null);
  async function mutate(url, body, message) {
    setBusy(true); setError('');
    try {
      const next = await postJson(url, body);
      setData(next); setDeletion(null); toast(message);
      const remaining = new Set((trash ? next.archived || [] : next.samples || []).map(s => s.id));
      setSelected(previous => previous.filter(id => remaining.has(id)));
      if (url === '/font/adjust') setAdjusting(false);
      if (url === '/font/select') leaveManage();
      if (url === '/characters/add') { setInput(''); setAdding(false); }
      if (url === '/characters/delete') setPicked([]);
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }
  const samples = data?.samples || [];
  const archived = data?.archived || [];
  const members = data?.members || [];
  const defaults = new Map(members.map(m => [m.char, `${m.run}/${m.sample_id}`]));
  const pending = data?.pending || { added: [], removed: [], replaced: [] };
  const pendingKind = useMemo(() => {
    const next = new Map();
    for (const char of pending.added || []) next.set(char, 'added');
    for (const char of pending.replaced || []) next.set(char, 'replaced');
    for (const char of pending.removed || []) next.set(char, 'removed');
    return next;
  }, [pending.added, pending.removed, pending.replaced]);
  const groups = useMemo(() => {
    const next = new Map((data?.characters || []).map(c => [c, []]));
    for (const s of data?.samples || []) {
      if (!next.has(s.char)) next.set(s.char, []);
      next.get(s.char).push(s);
    }
    for (const char of pending.removed || []) {
      if (!next.has(char)) next.set(char, []);
    }
    return next;
  }, [data, pending.removed]);
  const visible = [...groups].filter(([char, entries]) => {
    if (query && !char.includes(query) && !`U+${char.codePointAt(0).toString(16)}`.toLowerCase().includes(query.toLowerCase())) return false;
    if (batch && !entries.some(s => s.run === batch)) return false;
    if (filter === 'empty' && entries.some(s => s.usable)) return false;
    if (filter === 'filled' && !entries.some(s => s.usable)) return false;
    if (filter === 'default' && !defaults.has(char)) return false;
    return true;
  });
  const detail = trash ? archived : (groups.get(activeChar) || []);
  const formal = !trash && activeChar ? detail.filter(s => defaults.get(s.char) === s.id) : [];
  const ordered = !trash && activeChar
    ? [...formal, ...detail.filter(s => defaults.get(s.char) !== s.id)]
    : detail;
  const context = activeChar ? [activeChar] : [];
  const photoUrl = `/photos?${activeChar ? `char=${encodeURIComponent(activeChar)}&` : ''}${context.length ? `chars=${encodeURIComponent(context.join(''))}` : ''}`;
  const batches = [...new Set(samples.map(s => s.run))];
  function askDeleteCharacters(chars) {
    setDeletion({ chars, count: chars.reduce((n, c) => n + (groups.get(c)?.length || 0), 0) });
  }
  function addCharacters(e) {
    e.preventDefault();
    try {
      const chars = [...new Set(parseCells(input))];
      if (!chars.length) throw new Error('请输入需要添加的字符。');
      const added = chars.filter(c => !groups.has(c)).length;
      const skipped = chars.length - added;
      mutate('/characters/add', { characters: input }, skipped ? `已添加 ${added} 个字符，${skipped} 个已存在的字符已跳过。` : `已添加 ${added} 个字符。`);
    } catch (e) { setError(e.message); }
  }
  async function importCharset(file) {
    setError('');
    try {
      if (!file) return;
      const name = (file.name || '').toLowerCase();
      if (!( /\.(txt|csv|tsv)$/.test(name) || (file.type || '').startsWith('text/') )) {
        throw new Error('请选择 TXT、CSV 或 TSV 字表。');
      }
      if (file.size > 100000) throw new Error('字表文件过大，请分批导入。');
      let text = (await file.text()).replace(/^\uFEFF/, '');
      if (name.endsWith('.csv') || name.endsWith('.tsv')) text = text.replace(/[,\t]/g, '\n');
      const next = input.trim() ? `${input.trim()}\n${text}` : text;
      if (next.length > 50000) throw new Error('字表过长，请分批导入。');
      parseCells(next);
      setInput(next);
    } catch (e) { setError(e.message); }
  }
  const selectedGlyphs = detail.filter(s => selected.includes(s.id));
  const adjustable = selectedGlyphs.filter(s => s.usable);
  function toggleGlyph(id) { setSelected(previous => previous.includes(id) ? previous.filter(value => value !== id) : [...previous, id]); }
  const pick = selectedGlyphs[0];
  const canSetFormal = !trash && selectedGlyphs.length === 1 && pick?.usable && defaults.get(pick.char) !== pick.id;
  const canUnsetFormal = !trash && selectedGlyphs.some(s => defaults.get(s.char) === s.id);
  async function restoreSelected() {
    if (!selected.length) return;
    setBusy(true); setError('');
    try {
      for (const id of selected) await postJson('/library/archive', { kind: 'sample', id, restore: true });
      toast('所选字形已恢复。');
    } catch (e) { setError(e.message); }
    finally {
      try { setData(await getJson('/api/font')); setSelected([]); } catch (e) { setError(e.message); }
      setBusy(false);
    }
  }
  function glyphCard(s) {
    const chosen = defaults.get(s.char) === s.id;
    const isPicked = selected.includes(s.id);
    const quality = s.usable ? '' : (STATUS[s.status] || s.status);
    const content = <div className="glyph-frame"><img draggable={false} loading="lazy" className={view === 'vector' && s.usable ? 'is-vector' : undefined} src={view === 'vector' && !s.usable ? s.gray : s[view]} alt={`${s.char}的字形`} /></div>;
    return <article className={`glyph-card${chosen ? ' is-default' : ' is-informal'}${managing && isPicked ? ' is-picked' : ''}`} key={s.id}>
      {managing
        ? <div className={trash ? "glyph-card-top" : "glyph-selection-overlay"}><label className="trash-pick"><input type="checkbox" aria-label={`选择字形 ${s.char} ${s.id}`} disabled={busy} checked={isPicked} onChange={() => toggleGlyph(s.id)} />{trash ? <strong>{s.char}</strong> : null}</label>{trash && quality ? <span className="glyph-status">{quality}</span> : null}</div>
        : trash
          ? <div className="glyph-card-top"><strong>{s.char}</strong>{quality ? <span className="glyph-status">{quality}</span> : null}</div>
          : null}
      {managing
        ? <button type="button" className="glyph-card-hit" disabled={busy} onClick={() => toggleGlyph(s.id)} aria-label={`选择${chosen ? '正式' : '非正式'}字形 ${s.id}`} aria-pressed={isPicked}>{content}</button>
        : trash
          ? content
          : <Link className="glyph-card-hit" draggable={false} to={`/glyph/${encodeURIComponent(s.run)}/${encodeURIComponent(s.sample_id)}`} aria-label={`编辑 ${s.char} 的${chosen ? '正式' : '非正式'}字形 ${s.id}`}>{content}</Link>}
      {quality && !trash ? <span className="glyph-status">{quality}</span> : null}
    </article>;
  }
  if (!data) return <Page><ErrorNote error={error || exportError} /><p className="muted">正在加载…</p></Page>;
  const glyphManage = <>
    {!trash && <button type="button" disabled={busy || !canSetFormal} onClick={() => mutate('/font/select', { sample: pick.id, remove: false }, '已设为正式字形。')}>设为正式</button>}
    {!trash && <button type="button" className="secondary" disabled={busy || !canUnsetFormal} onClick={() => {
      const current = selectedGlyphs.find(s => defaults.get(s.char) === s.id);
      if (current) mutate('/font/select', { sample: current.id, remove: true }, '已取消正式字形。');
    }}>取消正式</button>}
    {!trash && <button type="button" className="secondary" disabled={busy || !adjustable.length} onClick={() => { setOptions({ ...ORIGINAL }); setError(''); setAdjusting(true); }}>调整</button>}
    {trash ? <button type="button" className="secondary" disabled={busy || !selected.length} onClick={restoreSelected}>恢复</button> : null}
    <button type="button" className="danger" disabled={busy || !selected.length} onClick={() => setDeletion({ ids: [...selected], permanent: trash })}>{trash ? '永久删除' : '删除'}</button>
  </>;
  const manageActions = library
    ? <button type="button" className="danger" disabled={busy || !picked.length} onClick={() => askDeleteCharacters(picked)}>删除</button>
    : glyphManage;
  const batchToolbar = <ManageToolbar managing={managing} onEnter={enterManage} onLeave={leaveManage} count={library ? picked.length : selected.length} total={library ? visible.length : detail.length} busy={busy} onSelectAll={() => library ? setPicked(visible.map(([c]) => c)) : setSelected(detail.map(s => s.id))} onClear={() => library ? setPicked([]) : setSelected([])}>{manageActions}</ManageToolbar>;
  return <Page>
    {library && <LiveFontTools />}
    <div className={`action-bar project-heading${managing ? ' is-managing' : ''}`}>
      <h1>{trash ? '字形回收站' : activeChar ? activeChar : '字符库'}</h1>
      <div className="actions">
        {(activeChar || trash) && detail.length > 0 && <div className="view-switch"><SelectMenu ariaLabel="查看方式" value={view} onChange={setView} options={[{ value: 'vector', label: '矢量' }, { value: 'gray', label: '原图' }, { value: 'binary', label: '黑白' }]} /></div>}
        {!trash && <><Link className="button secondary with-icon" to={context.length ? templateUrl(context) : '/templates'}><FileIcon {...iconSm} />生成模板</Link><Link className="button secondary with-icon" to={photoUrl}><CameraIcon {...iconSm} />导入素材</Link></>}
        {library && <button type="button" className="with-icon" onClick={() => { setError(''); setAdding(true); }}><PlusIcon {...iconSm} />添加字符</button>}
        {!library && (trash || detail.length > 0) && batchToolbar}
      </div>
    </div>
    <ErrorNote error={adding || adjusting ? '' : error} />
    {deletion ? <ConfirmDialog open title={deletion.chars ? `删除 ${deletion.chars.length} 个字符？` : `${deletion.permanent ? '永久删除' : '删除'} ${deletion.ids?.length || 0} 个字形？`} busy={busy} onCancel={() => setDeletion(null)}
      onConfirm={() => deletion.chars ? mutate('/characters/delete', { characters: deletion.chars.map(c => `U+${c.codePointAt(0).toString(16)}`).join(' ') }, '字符已删除，关联字形已移入回收站。') : mutate(deletion.permanent ? '/library/delete' : '/library/trash', { ids: deletion.ids }, deletion.permanent ? '字形已永久删除。' : '字形已移入回收站，字符保留。')}>
      {deletion.chars ? `关联的 ${deletion.count} 个字形会移入回收站，并取消默认选择。空字符会从字符库移除。` : deletion.permanent ? '将永久删除字形文件，无法恢复。字符和已导出的字体不受影响。' : '字形移入回收站，默认选择会取消；字符仍保留，可以继续补充字形。'}
    </ConfirmDialog> : null}
    <Dialog open={adding && !activeChar && !trash} title="添加字符" busy={busy} onClose={() => { if (!busy) { setAdding(false); setInput(''); setError(''); } }} className="character-dialog">
      <form onSubmit={addCharacters} onDragOver={e => e.preventDefault()} onDrop={e => { e.preventDefault(); importCharset(e.dataTransfer.files?.[0]); }}>
        <label htmlFor="new-characters">添加单个字符或粘贴一段文字</label>
        <textarea id="new-characters" value={input} onChange={e => setInput(e.target.value)} placeholder="例如：春风又绿江南岸；也支持 U+5B57。也可导入 TXT 字表。" maxLength={50000} />
        <ErrorNote error={error} />
        <div className="actions">
          <label className="button secondary with-icon file-label">
            <FileIcon {...iconSm} />导入字表
            <input type="file" accept=".txt,.csv,.tsv,text/plain,text/csv" onChange={e => { importCharset(e.target.files?.[0]); e.target.value = ''; }} />
          </label>
          <button disabled={busy || !input.trim()}>添加到字符库</button>
          <button type="button" className="secondary" disabled={busy} onClick={() => { setAdding(false); setInput(''); setError(''); }}>取消</button>
        </div>
      </form>
    </Dialog>
    {!activeChar && !trash ? <>
      <div className="library-toolbar">
        <div className="library-filters">
          <div><label htmlFor="character-search">搜索</label><input id="character-search" value={query} onChange={e => { setQuery(e.target.value); setPicked([]); }} placeholder="字 或 Unicode编码" /></div>
          <div><label htmlFor="character-filter">字形</label><SelectMenu id="character-filter" value={filter} onChange={value => { setFilter(value); setPicked([]); }} options={[{ value: 'all', label: '全部字符' }, { value: 'empty', label: '暂无正式字形' }, { value: 'filled', label: '已有正式字形' }, { value: 'default', label: '已指定正式字形' }]} /></div>
          <div><label htmlFor="character-batch">来源批次</label><SelectMenu id="character-batch" value={batch} onChange={value => { setBatch(value); setPicked([]); }} options={[{ value: '', label: '全部批次' }, ...batches.map(id => ({ value: id, label: id }))]} /></div>
        </div>
        {<div className="library-toolbar-actions">
          {batchToolbar}
          <button type="button" className="with-icon" onClick={() => setParams({ view: 'trash' })}><TrashIcon {...iconSm} />回收站</button>
        </div>}
      </div>
      <div className="character-grid" aria-label="字符列表">{visible.map(([char, entries]) => {
        const preview = entries.find(s => s.id === defaults.get(char));
        const kind = pendingKind.get(char);
        const kindLabel = kind === 'removed' ? '已从字体移除，待更新' : kind === 'added' ? '新增到字体，待更新' : kind === 'replaced' ? '字形已更换，待更新' : '';
        return <div className={`character-entry${managing && picked.includes(char) ? ' is-picked' : ''}`} key={char}>
          {managing && <label className="character-pick"><input type="checkbox" disabled={busy} checked={picked.includes(char)} aria-label={`选择字符 ${char}`} onChange={e => setPicked(previous => e.target.checked ? [...previous, char] : previous.filter(c => c !== char))} /></label>}
          <button type="button" className={`character-tile${kind ? ` is-font-${kind}` : defaults.has(char) ? '' : ' is-font-informal'}`} disabled={busy} aria-pressed={managing ? picked.includes(char) : undefined} onClick={() => managing ? setPicked(previous => previous.includes(char) ? previous.filter(c => c !== char) : [...previous, char]) : setParams({ char })} aria-label={managing ? `选择字符 ${char}` : `${char}，${entries.length} 个字形，${defaults.has(char) ? '已指定正式字形' : '未指定正式字形'}，打开字形${kindLabel ? `，${kindLabel}` : ''}`}>
            <span className="character-preview-wrap">
              {preview ? <img className="character-preview is-vector" src={preview.vector} alt="" loading="lazy" /> : <span className="character-standard character-placeholder">{char.trim() ? char : '空格'}</span>}
              {entries.length > 1 ? <span className="character-count">{entries.length}</span> : null}
            </span>
          </button>
        </div>;
      })}</div>
      {!visible.length && <section className="panel"><p className="muted">{groups.size ? '没有匹配的字符' : '暂无字符'}</p></section>}
    </> : <section className="character-detail">
      {!trash && managing && selectedGlyphs.some(s => !s.usable) && <p className="hint">空白或触边字形不参与调整。</p>}
      {!detail.length
        ? <div className="panel empty-character"><p className="muted">{trash ? '回收站为空。' : '还没有这个字的字形。导入照片取字，或打印模板书写后导入。'}</p></div>
        : <div className="glyph-grid">{(trash || !activeChar ? detail : ordered).map(glyphCard)}</div>}
    </section>}
    <Dialog open={adjusting} title={`统一调整 ${adjustable.length} 个字形`} busy={busy} onClose={() => setAdjusting(false)} className="batch-glyph-dialog">
      <AdjustmentFields value={options} onChange={setOptions} disabled={busy} />
      <div className="batch-glyph-previews">{adjustable.map(s => <div className="glyph-frame" key={s.id}><img className="is-vector" loading="lazy" src={adjustmentPreview(s.id, options)} alt={`${s.char}调整预览`} /></div>)}</div>
      <ErrorNote error={error} />
      <div className="actions"><button type="button" className="text-button" disabled={busy} onClick={() => setOptions({ ...ORIGINAL })}>恢复原始</button><button disabled={busy || !adjustable.length} onClick={() => mutate('/font/adjust', { ids: adjustable.map(s => s.id), adjustment: options }, '所选字形修正已保存，请更新字体。')}>保存修正</button><button className="secondary" disabled={busy} onClick={() => setAdjusting(false)}>取消</button></div>
    </Dialog>
  </Page>;
}
