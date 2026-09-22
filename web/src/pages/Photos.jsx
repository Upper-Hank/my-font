import ManagedRecords from '../components/ManagedRecords.jsx';
import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { getJson, postForm } from '../api.js';
import ChevronDownIcon from '@uplus-icon/react/icons/chevron-down';
import ChevronRightIcon from '@uplus-icon/react/icons/chevron-right';
import CloseIcon from '@uplus-icon/react/icons/close';
import PlusIcon from '@uplus-icon/react/icons/plus';
import ScanIcon from '@uplus-icon/react/icons/scan';
import { ErrorNote, IconButton, Page, iconProps, iconSm } from '../ui.jsx';
import SelectMenu from '../SelectMenu.jsx';

export default function Photos() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [files, setFiles] = useState([]);
  const [template, setTemplate] = useState(params.get('template') || '');
  const [dpi, setDpi] = useState('300');
  const [threshold, setThreshold] = useState('');
  const [optionsOpen, setOptionsOpen] = useState(false);
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
    form.append('template', template);
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
        <h2>照片转字符</h2><p className="hint">上传书写照片，提取后先整理结果，再加入字符库。</p>
        {params.get('chars') && <p className="hint">本次补充：{params.get('chars')}。字形对应的字符以模板为准，可在整理时修正。</p>}
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
              <label htmlFor="template-select">对应模板</label>
              <SelectMenu
                id="template-select"
                ariaLabel="对应模板"
                value={template}
                onChange={setTemplate}
                options={[
                  { value: '', label: '自动识别照片上的模板' },
                  ...data.templates.map((item) => ({
                    value: item.id,
                    label: item.system || item.mode === 'generic' ? `${item.title}（自由书写）` : item.title,
                  })),
                ]}
              />
              <details className="process-options icon-disclosure" onToggle={(event) => setOptionsOpen(event.currentTarget.open)}>
                <summary>
                  {optionsOpen ? <ChevronDownIcon {...iconSm} /> : <ChevronRightIcon {...iconSm} />}
                  处理选项
                </summary>
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
                  <input type="number" min="1" max="254" placeholder="自动；工程调试时才填写" value={threshold} onChange={(e) => setThreshold(e.target.value)} />
                </label>
              </details>
              <ErrorNote error={error} />
              <button className="full with-icon" type="submit" disabled={busy || !files.length}><ScanIcon {...iconSm} />{busy ? '正在校正…' : '校正并预览'}</button>
            </div>
        </form>
      </section>
      <ManagedRecords title="整理空间" hint="照片预览和待整理结果会保留，可以随时继续。"
        items={[...(data.pending || []).map(item => ({ ...item, kind: 'run', title: '继续整理字形', to: `/run/${item.id}` })), ...data.previews.map(item => ({ ...item, kind: 'preview', title: '照片预览', to: `/preview/${item.id}` }))]}
        onRefresh={async () => setData(await getJson('/api/photos'))} />
      {(data.runs.length > 0 || data.archived_runs?.length > 0) && <ManagedRecords title="已完成转换" hint="删除转换记录不会删除已经加入的字形。"
        items={[...data.runs, ...(data.archived_runs || [])].map(item => ({ ...item, kind: 'run', title: '查看转换结果', to: `/run/${item.id}` }))}
        onRefresh={async () => setData(await getJson('/api/photos'))} />}
      {data.archived_previews?.length > 0 && <ManagedRecords title="任务回收站" recoverable
        items={data.archived_previews.map(item => ({ ...item, kind: 'preview', title: '照片预览' }))}
        onRefresh={async () => setData(await getJson('/api/photos'))} />}
    </Page>
  );
}
