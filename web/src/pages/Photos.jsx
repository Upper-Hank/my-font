import ManagedRecords from '../components/ManagedRecords.jsx';
import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { getJson, postForm } from '../api.js';
import CloseIcon from '@uplus-icon/react/icons/close';
import PlusIcon from '@uplus-icon/react/icons/plus';
import ScanIcon from '@uplus-icon/react/icons/scan';
import { ErrorNote, IconButton, Page, Disclosure, iconProps, iconSm } from '../ui.jsx';
import SelectMenu from '../SelectMenu.jsx';

export default function Photos() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [files, setFiles] = useState([]);
  const [template, setTemplate] = useState(params.get('template') || '');
  const [dpi, setDpi] = useState('300');
  const [threshold, setThreshold] = useState('');
  const [source, setSource] = useState(params.get('template') ? 'template' : 'auto');
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getJson('/api/photos').then(setData).catch((reason) => setError(reason.message));
  }, []);

  function addFiles(incoming) {
    const next = [...files];
    for (const file of incoming) {
      if (!next.some(item => item.name === file.name && item.size === file.size && item.lastModified === file.lastModified)) next.push(file);
    }
    if (next.length > 8) { setError('最多 8 张，请移除部分照片后再添加。'); return; }
    setFiles(next); setError('');
  }

  async function submit(event) {
    event.preventDefault();
    if (!files.length) { setError('请选择 1–8 张照片。'); return; }
    setBusy(true);
    setError('');
    const form = new FormData();
    files.forEach((file) => form.append('photos', file));
    form.append('source', source);
    form.append('template', source === 'free' ? '' : template);
    form.append('return_char', params.get('char') || '');
    form.append('dpi', dpi);
    form.append('threshold', threshold);
    try {
      const result = await postForm('/prepare', form);
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
      <section className="panel">
        <h2>导入素材</h2><p className="hint">普通照片、扫描稿或模板照片，都可以提取字形，调整后收入同一份字体。</p>
        {params.get('chars') && <p className="hint">本次补充：{params.get('chars')}。模板字符会预先填入，也可以重新指定。</p>}
        <form className="photo-upload" onSubmit={submit}>
            <div className="photo-upload-stage">
              <label className={`drop-zone${dragging ? ' dragging' : ''}`}
                onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
                onDragLeave={() => setDragging(false)}
                onDrop={(e) => { e.preventDefault(); setDragging(false); addFiles([...e.dataTransfer.files]); }}>
                <span className="upload-symbol"><PlusIcon size={28} weight={1.5} aria-hidden /></span>
                <strong>选择或拖入照片</strong>
                <span>JPEG / PNG / HEIC / TIFF · 最多 8 张</span>
                <input name="photos" type="file" accept="image/*,.heic,.heif" multiple
                  disabled={busy} onChange={(e) => { addFiles([...e.target.files]); e.target.value = ''; }} />
              </label>
              {files.length ? (
                <ul className="file-list">
                  {files.map((file, index) => <li key={`${file.name}-${file.lastModified}-${file.size}`}><span>{file.name} · {(file.size / 1024 / 1024).toFixed(1)} MB</span><IconButton label={`移除 ${file.name}`} disabled={busy} onClick={() => setFiles(current => current.filter((_, i) => i !== index))}><CloseIcon {...iconProps} /></IconButton></li>)}
                </ul>
              ) : null}
            </div>
            <div className="photo-upload-options">
              <label htmlFor="source-select">素材类型</label>
              <SelectMenu id="source-select" ariaLabel="素材类型" value={source} onChange={value => { setSource(value); if (value !== 'template') setTemplate(''); }} options={[
                { value: 'auto', label: '自动判断，加载可识别的模板预设' },
                { value: 'free', label: '普通照片 / 扫描稿，直接取字' },
                { value: 'template', label: '项目模板，加载格子与字符预设' },
              ]} />
              {source === 'template' && <><label htmlFor="template-select">模板预设</label>
              <SelectMenu
                id="template-select"
                ariaLabel="对应模板"
                value={template}
                onChange={setTemplate}
                options={[
                  { value: '', label: '自动识别模板' },
                  ...data.templates.map((item) => ({
                    value: item.id,
                    label: item.system || item.mode === 'generic' ? `${item.title}（自由书写）` : item.title,
                  })),
                ]}
              />
              </>}
              <Disclosure className="process-options" summary="提取选项">
                <label htmlFor="dpi-select">校正精度</label>
                <SelectMenu
                  id="dpi-select"
                  ariaLabel="校正精度"
                  value={dpi}
                  onChange={setDpi}
                  options={[
                    { value: '300', label: '标准' },
                    { value: '600', label: '高精' },
                  ]}
                />
                <label>墨迹阈值
                  <input type="number" min="1" max="254" placeholder="自动" value={threshold} onChange={(e) => setThreshold(e.target.value)} />
                </label>
              </Disclosure>
              <ErrorNote error={error} />
              <button className="full with-icon" type="submit" disabled={busy || !files.length}><ScanIcon {...iconSm} />{busy ? '正在准备素材…' : '进入取字'}</button>
            </div>
        </form>
      </section>
      <ManagedRecords title="继续转化" hint="取字区域和字形调整都可以保存，稍后继续。"
        items={[...(data.pending || []).map(item => ({ ...item, kind: 'run', title: '继续整理字形', to: `/run/${item.id}` })), ...data.previews.map(item => ({ ...item, kind: 'preview', title: '继续取字', to: `/preview/${item.id}` }))]}
        onRefresh={async () => setData(await getJson('/api/photos'))} />
      {(data.runs.length > 0 || data.archived_runs?.length > 0) && <ManagedRecords title="已完成转换" hint="删除转换记录不会删除已经加入的字形。"
        items={[...data.runs, ...(data.archived_runs || [])].map(item => ({ ...item, kind: 'run', title: '查看转换结果', to: `/run/${item.id}` }))}
        onRefresh={async () => setData(await getJson('/api/photos'))} />}
      {data.archived_previews?.length > 0 && <ManagedRecords title="任务回收站" recoverable
        items={data.archived_previews.map(item => ({ ...item, kind: 'preview', title: '继续取字' }))}
        onRefresh={async () => setData(await getJson('/api/photos'))} />}
    </Page>
  );
}
