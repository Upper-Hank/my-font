import { useCallback, useState } from 'react';
import { Link } from 'react-router-dom';
import TrashIcon from '@uplus-icon/react/icons/trash';
import UndoIcon from '@uplus-icon/react/icons/undo';
import { postJson } from '../api.js';
import { ConfirmDialog, ErrorNote, iconSm } from '../ui.jsx';
import ManageToolbar from './ManageToolbar.jsx';

// Shared behavior for saved templates, conversions and their trash lists.
export default function ManagedRecords({ title, items, onRefresh, recoverable = false, hint }) {
  const [managing, setManaging] = useState(false);
  const [picked, setPicked] = useState([]);
  const enterManage = useCallback(() => { setPicked([]); setManaging(true); }, []);
  const leaveManage = useCallback(() => { setPicked([]); setManaging(false); }, []);
  const [deleting, setDeleting] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const key = item => `${item.kind}:${item.id}`;
  const selected = items.filter(item => picked.includes(key(item)));
  function toggle(id) { setPicked(previous => previous.includes(id) ? previous.filter(value => value !== id) : [...previous, id]); }
  async function act(restore = false) {
    setBusy(true); setError('');
    try {
      for (const item of selected) await postJson(restore ? '/library/archive' : '/history/cleanup', { kind: item.kind, id: item.id, ...(restore ? { restore: true } : {}) });
      setDeleting(false);
    } catch (e) { setError(e.message); }
    finally {
      try { await onRefresh(); setPicked([]); setDeleting(false); } catch (e) { setError(e.message); }
      setBusy(false);
    }
  }
  return <section className="history managed-records">
    <div className="section-heading"><h2>{title} · {items.length}</h2><ManageToolbar managing={managing} onEnter={enterManage} onLeave={leaveManage} count={selected.length} total={items.length} busy={busy} onSelectAll={() => setPicked(items.map(key))} onClear={() => setPicked([])}>
      {recoverable && <button type="button" className="secondary with-icon" disabled={busy || !selected.length} onClick={() => act(true)}><UndoIcon {...iconSm} />恢复</button>}
      <button type="button" className="danger with-icon" disabled={busy || !selected.length} onClick={() => setDeleting(true)}><TrashIcon {...iconSm} />删除</button>
    </ManageToolbar></div>
    {hint && <p className="hint">{hint}</p>}<ErrorNote error={error} />
    {deleting ? <ConfirmDialog open title={`删除 ${selected.length} 条记录？`} busy={busy} onCancel={() => setDeleting(false)} onConfirm={() => act()}>这些记录及未加入的结果将永久删除。已加入字符库的字形保留。</ConfirmDialog> : null}
    <div className="record-grid">{items.map(item => <article className={`record${managing && picked.includes(key(item)) ? ' is-picked' : ''}`} key={key(item)}>
      {managing ? <label className="record-selection"><input type="checkbox" disabled={busy} checked={picked.includes(key(item))} onChange={() => toggle(key(item))} /><span><strong>{item.title}</strong><small>{item.description || item.id}</small></span></label> : item.to ? <Link to={item.to}><strong>{item.title}</strong><span>{item.description || item.id}</span></Link> : <><strong>{item.title}</strong><span>{item.description || item.id}</span></>}
    </article>)}</div>
    {!items.length && <p className="muted">暂无记录。</p>}
  </section>;
}
