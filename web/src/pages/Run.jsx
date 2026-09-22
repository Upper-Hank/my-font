import { useHeaderBack } from '../components/HeaderBack.jsx';
import { AdjustmentFields, ORIGINAL, adjustmentPreview } from '../components/GlyphAdjustment.jsx';
import RulerIcon from '@uplus-icon/react/icons/ruler';
import CheckIcon from '@uplus-icon/react/icons/check';
import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { getJson, postJson } from '../api.js';
import HistoryCleanupButton from '../components/HistoryCleanupButton.jsx';
import { useToast } from '../components/Toast.jsx';
import { ErrorNote, Page, iconSm, Disclosure } from '../ui.jsx';
const STATUS = { review: '可用', blank: '未写', edge: '触边，需检查' };
export default function Run() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [choices, setChoices] = useState([]);
  const [view, setView] = useState('gray');
  const [batchAdjustment, setBatchAdjustment] = useState({ ...ORIGINAL });
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [dirty, setDirty] = useState(false);
  const returnTo = data?.return_char ? `/results?char=${encodeURIComponent(data.return_char)}` : '/results';
  const toast = useToast();
  function receive(value) {
    setData(value);
    setChoices(value.choices || value.glyphs.map(g => ({ sample_id: g.sample_id, char: g.char || g.candidates?.[0]?.char || '', confirmed: false, keep: g.usable && g.has_vector })));
    setDirty(false);
  }
  useEffect(() => {
    let active = true;
    getJson(`/api/runs/${id}`).then(value => { if (active) receive(value); }).catch(e => { if (active) setError(e.message); });
    return () => { active = false; };
  }, [id]);
  useEffect(() => {
    if (!dirty) return;
    const prevent = e => { e.preventDefault(); e.returnValue = ''; };
    window.addEventListener('beforeunload', prevent);
    return () => window.removeEventListener('beforeunload', prevent);
  }, [dirty]);
  function edit(sample, patch) {
    setChoices(previous => previous.map(c => c.sample_id === sample ? { ...c, ...patch } : c));
    setDirty(true);
  }
  const save = useCallback(async (commit = false, leave = false) => {
    setBusy(true); setError('');
    try {
      receive(await postJson('/run/review', { run: id, choices, commit }));
      toast(commit ? '所选字形已加入对应字符，原有写法保留。' : '整理已保存，下次可以继续。');
      if (leave) navigate(returnTo);
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }, [id, choices, returnTo, navigate, toast]);
  const returnAfterSave = useCallback(() => save(false, true), [save]);
  useHeaderBack({ to: returnTo, label: data?.review_pending ? '保存并返回' : data?.return_char ? '返回字符字形' : '返回字符库', onClick: data?.review_pending ? returnAfterSave : undefined, disabled: busy });
  const kept = choices.filter(c => c.keep);
  const unconfirmed = kept.filter(c => data?.glyphs.find(g => g.sample_id === c.sample_id)?.matching_required && (!c.confirmed || Array.from(c.char).length !== 1)).length;
  return <Page><ErrorNote error={error} />{data ? <>
    <div className="action-bar">
      <div><h1>{data.review_pending ? '整理转换结果' : '转换结果'}</h1><p className="hint">{data.review_pending ? '候选来自已有字形的外观相似度，不代表识别概率。检查或手动修正字符；通用模板需逐字确认后入库。没有参考字形时请手动填写。' : '整理后的字形已加入字符库。照片和转换记录保留在这里供追溯。'}</p></div>
      <div className="actions">{data.review_pending ? <><button disabled={busy || !kept.length || unconfirmed > 0} onClick={() => save(true)}>{busy ? '保存中…' : `加入字符库 · ${kept.length} 个字形`}</button></> : null}</div>
    </div>
    {data.review_pending && <Disclosure className="panel batch-adjustment" summary={<><RulerIcon {...iconSm} />大小与位置修正</>}>
      <p className="hint">可保持原样，或先等比统一汉字大小，再调整缩放与居中。自动大小不放大标点和英文；居中应用到所选字形。</p>
      <AdjustmentFields value={batchAdjustment} onChange={setBatchAdjustment} disabled={busy} />
      <div className="actions adjustment-commit"><button type="button" className="text-button" disabled={busy} onClick={() => setBatchAdjustment({ ...ORIGINAL })}>恢复原始</button><button className="with-icon" disabled={busy || !kept.length} onClick={() => { setChoices(previous => previous.map(c => c.keep ? { ...c, adjustment: { ...batchAdjustment } } : c)); setDirty(true); setView('vector'); toast('已更新所选字形预览。保存整理或加入字符库后生效。'); }}><CheckIcon {...iconSm} />预览应用到所选字形 · {kept.length}</button></div>
    </Disclosure>}
    <div className="action-bar"><div className="segmented">{[['gray', '照片'], ['binary', '黑白'], ['vector', '矢量']].map(([key, label]) => <button key={key} className={view === key ? 'selected' : ''} onClick={() => setView(key)}>{label}</button>)}</div>{data.review_pending && <div className="actions"><span className="hint">{unconfirmed ? `${unconfirmed} 个字形待确认` : dirty ? '有未保存的修改' : '结果已保留，可稍后整理'}</span><button className="secondary" disabled={busy || !dirty} onClick={() => save()}>保存整理</button></div>}</div>
    <div className="glyph-grid">{data.glyphs.map(g => {
      const choice = choices.find(c => c.sample_id === g.sample_id);
      return <article className={`glyph-card${choice && !choice.keep ? ' review-excluded' : ''}`} key={g.sample_id}>
        <div className="glyph-heading"><strong>{choice?.char || g.char || `第 ${g.cell_id} 格`}</strong><span>{STATUS[g.status] || g.status}</span></div>
        <div className="glyph-frame"><img loading="lazy" className={view === 'vector' && g.has_vector ? 'is-vector' : undefined} src={view === 'vector' ? g.has_vector ? adjustmentPreview(`${id}/${g.sample_id}`, choice?.adjustment, 'run', choice?.char || g.char) : g.gray : g[view]} alt={`${g.char} · ${g.sample_id}`} /></div>
        <div className="sample-meta">{data.review_pending ? <><label>对应字符<input className="review-character" disabled={busy} value={choice?.char || ''} onChange={e => edit(g.sample_id, { char: e.target.value, confirmed: false })} aria-label={`${g.sample_id} 对应字符`} /></label>{g.candidates?.length > 0 && <div className="actions">{g.candidates.map(candidate => <button type="button" disabled={busy} key={candidate.char} onClick={() => edit(g.sample_id, { char: candidate.char, confirmed: false })}>{candidate.char} · 相似度 {Math.round(candidate.similarity * 100)}%</button>)}</div>}
        {g.matching_required && <button type="button" disabled={busy || !choice?.keep || Array.from(choice?.char || '').length !== 1 || choice?.confirmed} onClick={() => edit(g.sample_id, { confirmed: true })}>{choice?.confirmed ? '已确认匹配' : '确认对应字符'}</button>}
        <label className="review-choice"><input type="checkbox" disabled={busy} checked={Boolean(choice?.keep)} onChange={e => edit(g.sample_id, { keep: e.target.checked })} />保留这个字形</label></> : choice?.keep !== false ? <Link to={`/results?char=${encodeURIComponent(choice?.char || g.char)}`}>查看字符的全部字形</Link> : <span className="hint">未加入字符库</span>}</div>
      </article>;
    })}</div>
    <div className="action-bar character-detail-footer"><p className="hint">{data.review_pending ? '未加入的结果和原照片会保留，直到你删除本次记录。' : '删除转换记录不会删除已加入字符库的字形。'}</p><HistoryCleanupButton kind="run" id={id} label={data.review_pending ? '删除这次待整理结果' : '删除这次记录'} onComplete={() => navigate('/photos')} onError={setError} /></div>
  </> : <p>正在加载…</p>}</Page>;
}
