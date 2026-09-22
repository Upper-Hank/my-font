import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { getJson, postJson } from '../api.js';
import { ErrorNote, Page } from '../ui.jsx';

export default function Conflicts() {
  const { id } = useParams();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const run = params.get('run') || '';
  const exclude = params.get('exclude') || '';
  const [data, setData] = useState(null);
  const [picked, setPicked] = useState({});
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getJson(`/api/projects/${id}/conflicts?run=${encodeURIComponent(run)}&exclude=${encodeURIComponent(exclude)}`)
      .then(setData)
      .catch((reason) => setError(reason.message));
  }, [id, run, exclude]);

  async function submit(policy) {
    setBusy(true);
    setError('');
    const replace_chars = Object.entries(picked).filter(([, on]) => on).map(([char]) => char).join('');
    try {
      const result = await postJson('/project/add', {
        project: id, run, exclude, decided: true, policy, replace_chars,
      });
      if (result.redirect) navigate(result.redirect);
    } catch (reason) {
      setError(reason.message);
    } finally {
      setBusy(false);
    }
  }

  if (!data) return <Page title="选择重复的字"><p className="muted">{error || '正在加载…'}</p></Page>;

  return (
    <Page title="选择重复的字">
      <div className="panel">
        <p className="lede">这批可以新加入 <strong>{data.added}</strong> 字，另有 <strong>{data.duplicates.length}</strong> 个字与项目重复。</p>
        <p className="muted">重复字：{data.duplicates.map((d) => d.char).join('')}</p>
        <div className="actions" style={{ margin: '16px 0' }}>
          <button type="button" className="secondary" disabled={busy} onClick={() => submit('skip')}>全部保留项目已有</button>
          <button type="button" disabled={busy} onClick={() => submit('replace')}>全部改用这批新字</button>
        </div>
        <p>或者勾选要用这批覆盖的字，其余仍保留项目里已有的：</p>
        <div className="dup-grid">
          {data.duplicates.map((item) => (
            <label className="dup-item" key={item.unicode}>
              <input type="checkbox" checked={!!picked[item.char]}
                onChange={(e) => setPicked((current) => ({ ...current, [item.char]: e.target.checked }))} />
              <span>{item.char}</span>
            </label>
          ))}
        </div>
        <ErrorNote error={error} />
        <button type="button" className="full" disabled={busy} onClick={() => submit('pick')}>按勾选加入</button>
      </div>
    </Page>
  );
}
