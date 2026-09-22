import ChevronRightIcon from '@uplus-icon/react/icons/chevron-right';
import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { getJson, postJson } from '../api.js';
import { ErrorNote, Page, iconSm } from '../ui.jsx';
import SelectMenu from '../SelectMenu.jsx';

export default function Project() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [run, setRun] = useState('');
  const [error, setError] = useState('');
  const [adding, setAdding] = useState(false);
  const [building, setBuilding] = useState(false);

  useEffect(() => {
    getJson(`/api/projects/${id}`).then((payload) => {
      setData(payload);
      setRun(payload.runs[0]?.id || '');
    }).catch((reason) => setError(reason.message));
  }, [id]);

  async function add(event) {
    event.preventDefault();
    setAdding(true);
    setError('');
    try {
      const result = await postJson('/project/add', { project: id, run });
      if (result.redirect) navigate(result.redirect);
    } catch (reason) {
      setError(reason.message);
    } finally {
      setAdding(false);
    }
  }

  async function build() {
    setBuilding(true);
    setError('');
    try {
      const result = await postJson('/project/build', { project: id });
      if (result.redirect) navigate(result.redirect);
    } catch (reason) {
      setError(reason.message);
    } finally {
      setBuilding(false);
    }
  }

  if (!data) return <Page title="字体项目"><p className="muted">{error || '正在加载…'}</p></Page>;

  return (
    <Page title={data.title}>
      <p className="lede">把多批模板的字收进同一个字体。单份模板有多少格，不会限制这个项目最终有多少字。</p>
      <div className="pair">
        <form className="panel" onSubmit={add}>
          <label htmlFor="run">从已切字的批次加入</label>
          <SelectMenu
            id="run"
            ariaLabel="从已切字的批次加入"
            disabled={!data.runs.length}
            value={run}
            onChange={setRun}
            options={data.runs.length
              ? data.runs.map((item) => ({ value: item.id, label: `${item.title} · ${item.count} 个可加入的字 · ${item.id}` }))
              : [{ value: '', label: '还没有切字批次' }]}
          />
          <p className="hint">若与项目里已有字重复，会列出重复数量，并让你选择保留哪一批。</p>
          <ErrorNote error={error} />
          <button type="submit" disabled={adding || !data.runs.length}>{adding ? '正在核对该批字…' : '检查并加入'}</button>
        </form>
        <div className="panel">
          <p>当前项目 {data.count} 字。</p>
          <button type="button" className="with-icon" onClick={build} disabled={building || !data.count}>{building ? '正在生成字体与原图资源包…' : <>生成预览字体<ChevronRightIcon {...iconSm} /></>}</button>
        </div>
      </div>
      <section className="panel">
        <h2>已收入的批次</h2>
        <div className="record-grid">
          {data.sources.length ? data.sources.map((item) => (
            <div className="record" key={item.id}><strong>{item.id}</strong><span>{item.count} 字</span></div>
          )) : <p className="muted">还没有加入任何批次。</p>}
        </div>
        <p className="coverage">{data.characters || '（空）'}</p>
      </section>
    </Page>
  );
}
