export const ORIGINAL = { normalize: false, center_x: false, center_y: false, target: 800, scale: 1, reference: false, offset_x: 0, offset_y: 0 };
function adjustmentQuery(options) {
  const src = options || ORIGINAL;
  return JSON.stringify(Object.fromEntries(Object.keys(ORIGINAL).map(key => [key, src[key] ?? ORIGINAL[key]])));
}
export const adjustmentPreview = (sample, options, source = '', char = '') => `/api/glyph-preview?${new URLSearchParams({ sample, adjustment: adjustmentQuery(options), ...(source ? { source, char } : {}) })}`;

function rangeFill(min, max, value) {
  const lo = Number(min);
  const span = Number(max) - lo;
  if (!span) return '0%';
  return `${((Number(value) - lo) / span) * 100}%`;
}

function fitMode(value) {
  if (value.reference) return 'reference';
  if (value.normalize) return 'normalize';
  return 'original';
}

function AdjustmentSlider({ label, display, min, max, step, value, onChange }) {
  return <label className="adjustment-slider">
    <span><span>{label}</span><span>{display}</span></span>
    <input type="range" min={min} max={max} step={step} value={value} onChange={onChange} style={{ '--range': rangeFill(min, max, value) }} />
  </label>;
}

export function AdjustmentFields({ value, onChange, disabled }) {
  const change = patch => onChange({ ...value, ...patch });
  const fit = fitMode(value);
  return <fieldset className="adjustment-fields" disabled={disabled}>
    <div className="segmented adjustment-fit" role="group" aria-label="字面大小">
      {[['original', '保留原稿'], ['reference', '适配字面'], ['normalize', '最长边']].map(([key, label]) => (
        <button type="button" key={key} className={fit === key ? 'selected' : ''} aria-pressed={fit === key} onClick={() => change({ reference: key === 'reference', normalize: key === 'normalize' })}>{label}</button>
      ))}
    </div>
    {value.normalize && <AdjustmentSlider label="目标占字框" display={`${Math.round(value.target / 10)}%`} min="400" max="950" step="10" value={value.target} onChange={e => change({ target: Number(e.target.value) })} />}
    <AdjustmentSlider label="整体缩放" display={`${Math.round(value.scale * 100)}%`} min="0.25" max="4" step="0.05" value={value.scale} onChange={e => change({ scale: Number(e.target.value) })} />
    <div className="adjustment-toggles">
      <label className="review-choice"><input type="checkbox" checked={value.center_x} onChange={e => change({ center_x: e.target.checked })} />水平居中</label>
      <label className="review-choice"><input type="checkbox" checked={value.center_y} onChange={e => change({ center_y: e.target.checked })} />垂直居中</label>
    </div>
    <AdjustmentSlider label="水平位移" display={`${Number(((value.offset_x || 0) / 10).toFixed(1))}%`} min="-1000" max="1000" step="5" value={value.offset_x || 0} onChange={e => change({ offset_x: Number(e.target.value) })} />
    <AdjustmentSlider label="垂直位移" display={`${Number(((value.offset_y || 0) / 10).toFixed(1))}%`} min="-1000" max="1000" step="5" value={value.offset_y || 0} onChange={e => change({ offset_y: Number(e.target.value) })} />
  </fieldset>;
}
