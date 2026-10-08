import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { getJson, postJson } from '../api.js';
import HistoryCleanupButton from '../components/HistoryCleanupButton.jsx';
import SourceRegions from '../components/SourceRegions.jsx';
import { useHeaderBack } from '../components/HeaderBack.jsx';
import ScanIcon from '@uplus-icon/react/icons/scan';
import { ErrorNote, Page, iconSm } from '../ui.jsx';

const SOURCE = { free: '普通照片 / 扫描稿', generic: '通用模板预设', assigned: '指定字符模板预设' };
export default function Preview() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [dirty, setDirty] = useState(false);
  useEffect(() => {
    let active = true;
    getJson(`/api/previews/${id}`).then(value => { if (active) { if (value.converted) { navigate(`/run/${id}`, { replace: true }); return; } setData(value); setDirty(false); } }).catch(reason => { if (active) setError(reason.message); });
    return () => { active = false; };
  }, [id, navigate]);
  useEffect(() => {
    if (!dirty) return;
    const prevent = event => { event.preventDefault(); event.returnValue = ''; };
    window.addEventListener('beforeunload', prevent);
    return () => window.removeEventListener('beforeunload', prevent);
  }, [dirty]);
  const save = useCallback(async (convert = false, leave = false) => {
    setBusy(true); setError('');
    try {
      if (data.schema === 2) {
        const next = await postJson('/preview/save', { run: id, pages: data.pages.map(page => ({ page_id: page.page_id, regions: page.regions })) });
        setData(next); setDirty(false);
      }
      if (convert) {
        const result = await postJson('/confirm', { run: id, action: 'convert' });
        if (result.redirect) navigate(result.redirect);
      } else if (leave) navigate('/photos');
    } catch (reason) { setError(reason.message); }
    finally { setBusy(false); }
  }, [data, id, navigate]);
  const returnAfterSave = useCallback(() => save(false, true), [save]);
  useHeaderBack({ to: '/photos', label: dirty ? '保存并返回素材' : '返回素材', onClick: dirty ? returnAfterSave : undefined, disabled: busy });
  if (!data) return <Page><p className="muted">{error || '正在加载…'}</p></Page>;
  const count = data.pages.reduce((n, page) => n + (page.regions?.length || 0), 0);
  return <Page>
    <div className="action-bar">
      <div><h1>确定取字区域</h1><p className="hint">模板的格子与字符已预填，可以改变；普通照片直接框选需要的字。提取后继续调整字面大小和位置。</p></div>
      <div className="actions">
        {data.schema === 2 && <button type="button" disabled={busy || !dirty} onClick={() => save()}>保存取字</button>}
        <button type="button" className="with-icon" onClick={() => save(true)} disabled={busy || (data.schema === 2 && !count)}><ScanIcon {...iconSm} />{busy ? '正在处理…' : '提取并打磨字形'}</button>
      </div>
    </div>
    <ErrorNote error={error} />
    {data.pages.map(page => <section className="panel source-page" key={page.page_id}>
      <div className="section-heading"><h2>{page.source_name || '书写照片'}</h2><span className="hint">{SOURCE[page.source_kind] || '模板照片'}</span></div>
      {page.warning && <p className="notice">{page.warning}</p>}
      {data.schema === 2 ? <SourceRegions page={page} disabled={busy} returnChar={data.return_char} onChange={regions => { setData(previous => ({ ...previous, pages: previous.pages.map(p => p.page_id === page.page_id ? { ...p, regions } : p) })); setDirty(true); }} /> : <div className="pair"><figure><figcaption>上传原照</figcaption><img src={page.photo_url} alt="原始照片" /></figure><figure><figcaption>校正后的页面</figcaption><img src={page.scan_url} alt="校正后的页面" /></figure></div>}
    </section>)}
    <div className="action-bar"><p className="hint">{dirty ? '取字区域有未保存的修改。' : '素材与取字结果已保留，可稍后继续。'}</p><HistoryCleanupButton kind="preview" id={id} label="放弃并删除" onComplete={() => navigate('/photos')} onError={setError} /></div>
  </Page>;
}
