import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import CheckIcon from '@uplus-icon/react/icons/check';
import TrashIcon from '@uplus-icon/react/icons/trash';
import { getJson, postJson } from '../api.js';
import { useFontLive } from '../components/FontLive.jsx';
import { useHeaderBack } from '../components/HeaderBack.jsx';
import { AdjustmentFields, ORIGINAL, adjustmentPreview } from '../components/GlyphAdjustment.jsx';
import { useToast } from '../components/Toast.jsx';
import { ConfirmDialog, ErrorNote, Page, iconSm } from '../ui.jsx';

export default function Glyph() {
  const { run, sample: sampleId } = useParams();
  const id = `${run}/${sampleId}`;
  const [data, setData] = useState(null);
  const [options, setOptions] = useState({ ...ORIGINAL });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [deleting, setDeleting] = useState(false);
  const [previewFailed, setPreviewFailed] = useState(false);
  const [previewOptions, setPreviewOptions] = useState({ ...ORIGINAL });
  const [previewVersion, setPreviewVersion] = useState(0);
  const [preview, setPreview] = useState('vector');
  const [char, setChar] = useState('');
  const live = useFontLive();
  const toast = useToast();
  const sample = data?.samples.find(s => s.id === id);
  const chosen = data?.members.some(m => `${m.run}/${m.sample_id}` === id);
  const back = char ? `/results?char=${encodeURIComponent(char)}` : '/results';
  useHeaderBack({ to: back, label: '返回字符字形', disabled: busy });
  useEffect(() => {
    const timer = setTimeout(() => setPreviewOptions(options), 180);
    return () => clearTimeout(timer);
  }, [options]);
  useEffect(() => { setPreviewFailed(false); }, [id, preview, previewOptions, previewVersion]);
  useEffect(() => {
    setData(null); setError(''); setChar('');
    let active = true;
    getJson('/api/font').then(value => {
      if (!active) return;
      setData(value);
      const found = value.samples.find(s => s.id === id);
      if (found) { setOptions({ ...ORIGINAL, ...found.adjustment }); setPreviewOptions({ ...ORIGINAL, ...found.adjustment }); setChar(found.char); }
    }).catch(e => { if (active) setError(e.message); });
    return () => { active = false; };
  }, [id, previewVersion]);
  async function mutate(url, body, message) {
    setBusy(true); setError('');
    try {
      const next = await postJson(url, body);
      setData(next);
      live?.setData(next);
      toast(message);
      setDeleting(false);
    }
    catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }
  return <Page><ErrorNote error={error} />
    {!data ? error ? <button type="button" onClick={() => setPreviewVersion(value => value + 1)}>重新加载</button> : <p role="status">正在加载字形…</p> : !sample ? <div className="panel"><p>字形已移除或在回收站中。</p><Link className="button secondary" to={back}>查看字符的其他字形</Link></div> : <>
      <div className="action-bar glyph-page-heading"><div><h1><span className="glyph-page-char">{sample.char}</span><span className="badge">{chosen ? '正式字形' : '候选字形'}</span></h1></div><div className="actions">
        <button type="button" className={chosen ? 'glyph-default-toggle is-on' : undefined} aria-pressed={chosen} disabled={busy || !sample.usable} onClick={() => mutate('/font/select', { sample: id, remove: chosen }, chosen ? '已移到候选字形。' : '已设为正式字形。')}>{chosen ? '移到候选' : '用作正式字形'}</button>
        <button type="button" className="danger with-icon" disabled={busy} onClick={() => setDeleting(true)}><TrashIcon {...iconSm} />删除</button>
      </div></div>
      <div className="glyph-editor-layout">
        <section className="panel">
          <div className="glyph-editor-heading">
            <h2>预览</h2>
            <div className="segmented" role="group" aria-label="查看方式">
              {[['vector', '矢量'], ['photo', '原图'], ['binary', '黑白']].map(([key, label]) => (
                <button type="button" key={key} className={preview === key ? 'selected' : ''} aria-pressed={preview === key} onClick={() => setPreview(key)}>{label}</button>
              ))}
            </div>
          </div>
          <div className="glyph-frame glyph-editor-preview" aria-label="字形预览">
            <img
              className={preview === 'vector' && sample.usable ? 'is-vector' : undefined}
              src={preview === 'photo' ? sample.gray : preview === 'binary' ? sample.binary || sample.gray : sample.usable ? adjustmentPreview(id, previewOptions) : sample.gray}
              onError={() => setPreviewFailed(true)}
              onLoad={() => setPreviewFailed(false)}
              alt={preview === 'photo' ? `${sample.char}原始照片` : preview === 'binary' ? `${sample.char}黑白图` : `${sample.char}字形预览`}
            />
          </div>
          {previewFailed && <p className="form-error" role="alert">预览加载失败，请重试或切换原图。</p>}
        </section>
        <section className="panel">
          <div className="glyph-editor-heading">
            <h2>大小与位置</h2>
            <div className="actions adjustment-commit">
              <button type="button" className="secondary" disabled={busy || !sample.usable} onClick={() => setOptions({ ...ORIGINAL })}>恢复原始</button>
              <button className="with-icon" disabled={busy || !sample.usable} onClick={() => mutate('/font/adjust', { ids: [id], adjustment: options }, '修正已保存，请更新字体。')}><CheckIcon {...iconSm} />保存修正</button>
            </div>
          </div>
          <AdjustmentFields value={options} onChange={setOptions} disabled={busy || !sample.usable} />
          {!sample.usable && <p className="hint">空白或触边，无法调整或设为正式字形。</p>}
        </section>
      </div>
    </>}
    <ConfirmDialog open={deleting} title="删除这个字形？" busy={busy} onCancel={() => setDeleting(false)} onConfirm={() => mutate('/library/trash', { ids: [id] }, '字形已移入回收站，字符仍保留。')}>字形移入回收站，正式字形选择会取消，字符保留。</ConfirmDialog>
  </Page>;
}
