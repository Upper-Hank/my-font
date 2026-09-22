import ManagedRecords from '../components/ManagedRecords.jsx';
import ManageToolbar from '../components/ManageToolbar.jsx';
import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import PlusIcon from '@uplus-icon/react/icons/plus';
import FileIcon from '@uplus-icon/react/icons/file';
import GridIcon from '@uplus-icon/react/icons/grid';
import TrashIcon from '@uplus-icon/react/icons/trash';
import { getJson, postJson } from '../api.js';
import { ConfirmDialog, ErrorNote, Page, iconProps, iconSm } from '../ui.jsx';

const DRAFT_KEYS = ['handfont-canvas-v2', 'handfont-template-draft'];
const DRAFT_ID = 'draft';

function readDraft() {
  try {
    const stored = JSON.parse(sessionStorage.getItem('handfont-canvas-v2'));
    if (stored?.pages?.length && Array.isArray(stored.library)) return { title: stored.title, pages: stored.pages.length };
    const legacy = JSON.parse(sessionStorage.getItem('handfont-template-draft'));
    return Array.isArray(legacy?.cells) ? { title: legacy.title, pages: 1 } : null;
  } catch { return null; }
}

export default function TemplateLibrary() {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [draft, setDraft] = useState(readDraft);
  const [managing, setManaging] = useState(false);
  const [picked, setPicked] = useState([]);
  const [busy, setBusy] = useState(false);
  const [deletion, setDeletion] = useState(false);
  const enterManage = useCallback(() => { setPicked([]); setManaging(true); }, []);
  const leaveManage = useCallback(() => { setPicked([]); setManaging(false); }, []);
  useEffect(() => {
    let active = true;
    getJson('/api/templates').then(value => { if (active) setData(value); }).catch(e => { if (active) setError(e.message); });
    return () => { active = false; };
  }, []);
  const paper = data?.paper || (data?.records || []).find(item => item.system || item.id === 'paper');
  const records = (data?.records || []).filter(item => item.id !== paper?.id && !item.system);
  const managedIds = [...(draft ? [DRAFT_ID] : []), ...records.map(item => item.id)];
  function discardDraft() {
    DRAFT_KEYS.forEach(key => sessionStorage.removeItem(key));
    setDraft(null);
    setPicked(previous => previous.filter(id => id !== DRAFT_ID));
  }
  function togglePick(id) {
    setPicked(previous => previous.includes(id) ? previous.filter(item => item !== id) : [...previous, id]);
  }
  async function deletePicked() {
    setBusy(true);
    setError('');
    try {
      if (picked.includes(DRAFT_ID)) discardDraft();
      for (const id of picked.filter(item => item !== DRAFT_ID)) {
        await postJson('/history/cleanup', { kind: 'template', id });
      }
      setData(await getJson('/api/templates'));
      setPicked([]);
      setDeletion(false);
    } catch (e) { setError(e.message); }
    finally {
      try { setData(await getJson('/api/templates')); setPicked([]); setDeletion(false); } catch (e) { setError(e.message); }
      setBusy(false);
    }
  }
  function cardBody(item) {
    return <>
      <div className="template-card-cover">{item.cover}<small>{item.badge}</small></div>
      <strong>{item.title}</strong>
      <span>{item.description}</span>
    </>;
  }
  const refresh = async () => setData(await getJson('/api/templates'));
  return <Page>
    <div className="section-heading">
      <div><h2>生成模板</h2><p className="hint">指定字符模板自己排要写的字。通用书写纸是系统自带的空格纸，写完拍照后再认字，不能删除。</p></div>
      <ManageToolbar managing={managing} onEnter={enterManage} onLeave={leaveManage} count={picked.length} total={managedIds.length} busy={busy} onSelectAll={() => setPicked(managedIds)} onClear={() => setPicked([])}>
        <button type="button" className="danger with-icon" disabled={busy || !picked.length} onClick={() => setDeletion(true)}><TrashIcon {...iconSm} />删除</button>
      </ManageToolbar>
    </div>
    <ErrorNote error={error} />
    {deletion ? <ConfirmDialog open title={`删除 ${picked.length} 个模板？`} busy={busy} onConfirm={deletePicked} onCancel={() => { if (!busy) setDeletion(false); }}>
      删除模板不会影响已经切出来的字形。草稿会直接丢弃。
    </ConfirmDialog> : null}
    {paper ? <section className="template-library-section" aria-label="通用书写纸">
      <h3>通用书写纸</h3>
      <div className="template-library-grid">
        <Link className="template-library-card template-system-card" to={`/template/${paper.id}`}>
          {cardBody({ cover: <GridIcon {...iconProps} />, badge: '系统 · 不能删除', title: paper.title, description: '打印时选份数，写完再认字' })}
        </Link>
      </div>
    </section> : null}
    <section className={`template-library-section${managing ? ' is-managing' : ''}`} aria-label="指定字符模板">
      <h3>指定字符模板</h3>
      <div className={`template-library-grid${managing ? ' is-managing' : ''}`}>
      <Link className="template-library-card template-create-card" to="/template/new"><div className="template-card-cover"><PlusIcon size={28} weight={1.5} aria-hidden="true" /></div><strong>创建模板</strong><span>排指定要写的字</span></Link>
      {draft ? <div className={`template-library-card${managing ? ' is-managing' : ''}${managing && picked.includes(DRAFT_ID) ? ' is-picked' : ''}`}>
        {managing ? <label className="template-pick"><input type="checkbox" disabled={busy} checked={picked.includes(DRAFT_ID)} aria-label="选择草稿" onChange={() => togglePick(DRAFT_ID)} /></label> : null}
        {managing
          ? <button type="button" className="template-card-open" disabled={busy} aria-pressed={picked.includes(DRAFT_ID)} onClick={() => togglePick(DRAFT_ID)}>{cardBody({ cover: <FileIcon {...iconProps} />, badge: '未导出草稿', title: draft.title || '未命名模板', description: `${draft.pages} 页` })}</button>
          : <Link to="/template/draft">{cardBody({ cover: <FileIcon {...iconProps} />, badge: '未导出草稿', title: draft.title || '未命名模板', description: `${draft.pages} 页 · 继续编辑草稿` })}</Link>}
      </div> : null}
      {records.map(item => <div className={`template-library-card${managing ? ' is-managing' : ''}${managing && picked.includes(item.id) ? ' is-picked' : ''}`} key={item.id}>
        {managing ? <label className="template-pick"><input type="checkbox" disabled={busy} checked={picked.includes(item.id)} aria-label={`选择模板 ${item.title}`} onChange={() => togglePick(item.id)} /></label> : null}
        {managing
          ? <button type="button" className="template-card-open" disabled={busy} aria-pressed={picked.includes(item.id)} onClick={() => togglePick(item.id)}>{cardBody({ cover: <FileIcon size={28} weight={1.5} aria-hidden="true" />, badge: `${item.pages} 页`, title: item.title, description: `${item.characters} 个字块` })}</button>
          : <Link to={`/template/${item.id}`}>{cardBody({ cover: <FileIcon size={28} weight={1.5} aria-hidden="true" />, badge: item.mode === 'generic' ? `${item.pages} 页 · 通用` : `${item.pages} 页`, title: item.title, description: item.mode === 'generic' ? '自由书写 · 点击进入画布' : `${item.characters} 个字块 · 点击进入画布` })}</Link>}
      </div>)}
      </div>
    </section>
    {!data && !error ? <p className="hint" role="status">正在加载模板…</p> : null}
    {data?.archived?.length > 0 && <ManagedRecords title="模板回收站" recoverable items={data.archived.map(item => ({ ...item, kind: 'template', description: `${item.characters} 个字块 · ${item.pages} 页` }))} onRefresh={refresh} />}
  </Page>;
}
