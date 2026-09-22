import { useEffect, useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import { getJson } from '../api.js';
import DownloadIcon from '@uplus-icon/react/icons/download';
import GridIcon from '@uplus-icon/react/icons/grid';
import { ErrorNote, Page, iconSm } from '../ui.jsx';

function graphemes(text) {
  if (typeof Intl !== 'undefined' && Intl.Segmenter) {
    return [...new Intl.Segmenter('zh', { granularity: 'grapheme' }).segment(text)].map((part) => part.segment);
  }
  return [...text];
}

function TypesetStage({ text, size, tracking, leading, frames }) {
  const style = {
    fontFamily: 'myfont, sans-serif',
    fontSize: `${size}px`,
    letterSpacing: `${tracking}px`,
    lineHeight: String(leading),
  };
  if (!text) {
    return <div className="typeset-stage is-empty" style={style}><p className="muted">输入文字，看这套字在排版里的样子。</p></div>;
  }
  return (
    <div className={`typeset-stage${frames ? ' show-frames' : ''}`} style={style}>
      {graphemes(text).map((char, index) => (
        char === '\n'
          ? <br key={index} />
          : <span className={`typeset-char${/\s/u.test(char) ? ' is-space' : ''}`} key={index}>{char}</span>
      ))}
    </div>
  );
}

export default function Build() {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [sample, setSample] = useState('');
  const [size, setSize] = useState(52);
  const [tracking, setTracking] = useState(0);
  const [leading, setLeading] = useState(1.4);
  const [frames, setFrames] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    getJson(`/api/builds/${id}`).then((payload) => {
      setData(payload);
      setSample(payload.sample);
    }).catch((reason) => setError(reason.message));
  }, [id]);

  const missing = useMemo(() => {
    if (!data) return [];
    const covered = new Set([...data.characters]);
    return [...new Set([...sample].filter((c) => !/\s/u.test(c) && !covered.has(c)))];
  }, [data, sample]);

  if (!data) return <Page><p className="muted">{error || '正在加载…'}</p></Page>;

  return (
    <Page>
      <style>{`@font-face{font-family:myfont;src:url('${data.font}')}`}</style>
      <section className="panel typesetter">
        <div className="section-heading">
          <h2>试字</h2>
          <a href={`/download?p=builds/${id}/Preview.otf`} className="button with-icon"><DownloadIcon {...iconSm} />下载 OTF</a>
        </div>
        <div className="typeset-tools">
          <label className="size-control">
            字号
            <input type="range" min="24" max="120" value={size} aria-label="字号" onChange={(e) => setSize(Number(e.target.value))} />
            <output>{size}</output>
          </label>
          <label className="size-control">
            字距
            <input type="range" min="-12" max="40" value={tracking} aria-label="字间距" onChange={(e) => setTracking(Number(e.target.value))} />
            <output>{tracking}</output>
          </label>
          <label className="size-control">
            行距
            <input type="range" min="10" max="28" value={Math.round(leading * 10)} aria-label="行距" onChange={(e) => setLeading(Number(e.target.value) / 10)} />
            <output>{leading.toFixed(1)}</output>
          </label>
          <button type="button" className={`with-icon${frames ? '' : ' typeset-toggle'}`} aria-pressed={frames} onClick={() => setFrames((on) => !on)}>
            <GridIcon {...iconSm} />字框
          </button>
        </div>
        <label className="typeset-source-label">
          试打文本
          <textarea rows={3} spellCheck="false" value={sample} onChange={(e) => setSample(e.target.value)} />
        </label>
        <TypesetStage text={sample} size={size} tracking={tracking} leading={leading} frames={frames} />
        {missing.length ? <p className="notice">这些字还未采集，会显示为缺字或系统字体：{missing.join(' ')}</p> : null}
      </section>
      <ErrorNote error={error} />
    </Page>
  );
}
