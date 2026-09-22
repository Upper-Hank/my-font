import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { getJson, postJson } from '../api.js';
import HistoryCleanupButton from '../components/HistoryCleanupButton.jsx';
import ScanIcon from '@uplus-icon/react/icons/scan';
import { ErrorNote, Page, iconSm } from '../ui.jsx';

export default function Preview() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getJson(`/api/previews/${id}`).then(setData).catch((reason) => setError(reason.message));
  }, [id]);

  async function confirm() {
    setBusy(true);
    setError('');
    try {
      const result = await postJson('/confirm', { run: id, action: 'convert' });
      if (result.redirect) navigate(result.redirect);
    } catch (reason) {
      setError(reason.message);
    } finally {
      setBusy(false);
    }
  }

  if (!data) return <Page><p className="muted">{error || '正在加载…'}</p></Page>;

  return (
    <Page>
      <div className="action-bar">
        <p className="muted">字迹清楚、页面完整就可以切字。</p>
        <button type="button" className="with-icon" onClick={confirm} disabled={busy}><ScanIcon {...iconSm} />{busy ? '正在切字…' : '提取字形'}</button>
        <HistoryCleanupButton kind="preview" id={id} label="放弃并删除" onComplete={() => navigate('/photos')} onError={setError} />
      </div>
      <ErrorNote error={error} />
      {data.pages.map((page) => (
        <section className="panel" key={page.page_id}>
          {page.warning && <p className="notice">{page.warning} 格框会辅助定位；请检查局部形变。</p>}
          <div className="pair">
            <figure><figcaption>上传原照</figcaption><img src={page.photo_url} alt="原始照片" /></figure>
            <figure><figcaption>方向与光照校正 · {page.characters || ''} 字</figcaption><img src={page.scan_url} alt="校正后的页面" /></figure>
          </div>
        </section>
      ))}
      <Link to="/photos">重新选择照片</Link>
    </Page>
  );
}
