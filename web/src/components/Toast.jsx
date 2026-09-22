import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import CloseIcon from '@uplus-icon/react/icons/close';
import SuccessIcon from '@uplus-icon/react/icons/success';
import { iconSm } from '../ui.jsx';

const ToastContext = createContext(null);

export function ToastProvider({ children }) {
  const { pathname } = useLocation();
  const [toast, setToast] = useState(null);
  const hide = useCallback(() => setToast(null), []);
  const show = useCallback((message, extra = {}) => {
    setToast({ id: Date.now(), message, ...extra });
  }, []);
  useEffect(() => { setToast(null); }, [pathname]);
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(hide, 4200);
    return () => clearTimeout(timer);
  }, [toast, hide]);
  return (
    <ToastContext.Provider value={show}>
      {children}
      {toast ? (
        <div className="app-toast" role="status" aria-live="polite">
          <SuccessIcon {...iconSm} />
          <p>
            {toast.message}
            {toast.to ? <> <Link to={toast.to} onClick={hide}>{toast.action || '查看'}</Link></> : null}
          </p>
          <button type="button" aria-label="关闭提示" onClick={hide}><CloseIcon {...iconSm} /></button>
        </div>
      ) : null}
    </ToastContext.Provider>
  );
}

export function useToast() {
  const show = useContext(ToastContext);
  const fallback = useRef(() => {});
  return show || fallback.current;
}
