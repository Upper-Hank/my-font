import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { Link, useLocation, useSearchParams } from 'react-router-dom';
import DownloadIcon from '@uplus-icon/react/icons/download';
import KeyboardIcon from '@uplus-icon/react/icons/keyboard';
import { getJson, postJson } from '../api.js';
import { iconSm } from '../ui.jsx';

const FontLiveContext = createContext(null);

export function FontLiveProvider({ children }) {
  const [data, setData] = useState(null);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState('');
  useEffect(() => {
    let active = true;
    getJson('/api/font').then(value => { if (active) setData(value); }).catch(e => { if (active) setExportError(e.message); });
    return () => { active = false; };
  }, []);
  const apply = useCallback(next => { setData(next); setExportError(''); }, []);
  async function exportFont() {
    setExporting(true);
    setExportError('');
    try { setData(await postJson('/font/export', {})); }
    catch (e) { setExportError(e.message); }
    finally { setExporting(false); }
  }
  return <FontLiveContext.Provider value={{ data, setData: apply, exporting, exportError, exportFont }}>{children}</FontLiveContext.Provider>;
}

export function useFontLive() {
  return useContext(FontLiveContext);
}

export function LiveFontTools() {
  const { pathname } = useLocation();
  const [params] = useSearchParams();
  const live = useFontLive();
  const isHome = pathname === '/results' && !params.get('char') && params.get('view') !== 'trash';
  if (!isHome || !live?.data) return null;
  const { data, exporting, exportError, exportFont } = live;
  const ready = data.members?.length > 0;
  const build = data.export;
  const dirty = Boolean(data.dirty);
  return (
    <section className="font-status-bar" aria-label="当前字体">
      <div className="font-status-copy">
        <strong>当前字体 <span className="hint">{data.members?.length || 0} 个字</span></strong>
        {exporting ? <span className="hint" role="status">正在更新字体…</span> : null}
        {exportError ? <span className="form-error" role="alert">{exportError}</span> : null}
      </div>
      <div className="font-status-actions" role="group" aria-label="字体操作">
        <button type="button" disabled={exporting || !ready || (build && !dirty)} onClick={exportFont}>{exporting ? '更新中…' : build ? '更新字体' : '生成字体'}</button>
        {build ? <Link className="button secondary with-icon" to={`/build/${build.id}`}><KeyboardIcon {...iconSm} />试打</Link> : <button type="button" className="secondary with-icon" disabled><KeyboardIcon {...iconSm} />试打</button>}
        {build ? <a className="button secondary with-icon" href={`/download?p=builds/${build.id}/Preview.otf`}><DownloadIcon {...iconSm} />下载</a> : <button type="button" className="secondary with-icon" disabled><DownloadIcon {...iconSm} />下载</button>}
      </div>
    </section>
  );
}
