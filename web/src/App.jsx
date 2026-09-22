import Glyph from './pages/Glyph.jsx';
import { useState } from 'react';
import { HeaderBackContext } from './components/HeaderBack.jsx';
import ChevronLeftIcon from '@uplus-icon/react/icons/chevron-left';
import { iconSm } from './ui.jsx';
import { Navigate, NavLink, Route, Routes, useLocation, useSearchParams } from 'react-router-dom';
import BrandMark from './BrandMark.jsx';
import { FontLiveProvider } from './components/FontLive.jsx';
import { ToastProvider } from './components/Toast.jsx';
import ThemeToggle from './ThemeToggle.jsx';
import Templates from './pages/Templates.jsx';
import TemplateLibrary from './pages/TemplateLibrary.jsx';
import Photos from './pages/Photos.jsx';
import Preview from './pages/Preview.jsx';
import Run from './pages/Run.jsx';
import Fonts from './pages/Fonts.jsx';
import Build from './pages/Build.jsx';

export default function App() {
  const { pathname } = useLocation();
  const [backAction, setBackAction] = useState(null);
  const [params] = useSearchParams();
  const isCanvas = /^\/template\/[^/]+\/?$/.test(pathname);
  const isHome = pathname === '/results' && !params.get('char') && params.get('view') !== 'trash';
  const back = isCanvas
    ? '/templates'
    : pathname === '/photos' && params.get('char')
      ? `/results?char=${encodeURIComponent(params.get('char'))}`
      : '/results';
  const backLabel = backAction?.label || (isCanvas ? '返回模板库' : '返回字符库');
  return (
    <FontLiveProvider><ToastProvider><HeaderBackContext.Provider value={setBackAction}><div className={`shell${isCanvas ? ' canvas-shell' : ''}`}>
      <header className="app-header">
        <nav aria-label="字体工程">{isHome ? <NavLink className="project-home" to="/results" aria-label="字记"><BrandMark /></NavLink> : backAction?.onClick ? <button className="header-back with-icon" disabled={backAction.disabled} onClick={backAction.onClick}><ChevronLeftIcon {...iconSm} />{backAction.label}</button> : <NavLink className="header-back with-icon" aria-disabled={backAction?.disabled || undefined} onClick={event => { if (backAction?.disabled) event.preventDefault(); }} to={backAction?.to || back}><ChevronLeftIcon {...iconSm} />{backLabel}</NavLink>}</nav>
        <div className="header-tools">
          <ThemeToggle />
        </div>
      </header>
      <Routes>
        <Route path="/" element={<Navigate to="/results" replace />} />
        <Route path="/templates" element={<TemplateLibrary />} />
        <Route path="/template/new" element={<Templates key="new" />} />
        <Route path="/template/draft" element={<Templates key="draft" resumeDraft />} />
        <Route path="/template/:id" element={<Templates />} />
        <Route path="/photos" element={<Photos />} />
        <Route path="/preview/:id" element={<Preview />} />
        <Route path="/run/:id" element={<Run />} />
        <Route path="/glyph/:run/:sample" element={<Glyph />} />
        <Route path="/strokes/:run/:sample" element={<main><h1>笔画与部件</h1><p>计划在后续版本提供，第一版 MVP 不包含此功能。</p></main>} />
        <Route path="/results" element={<Fonts />} />
        <Route path="/project/:id/conflicts" element={<Navigate to="/results" replace />} />
        <Route path="/project/:id" element={<Navigate to="/results" replace />} />
        <Route path="/build/:id" element={<Build />} />
      </Routes>
    </div></HeaderBackContext.Provider></ToastProvider></FontLiveProvider>
  );
}
