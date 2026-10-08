import { useEffect, useId, useRef, useState } from 'react';
import ChevronDownIcon from '@uplus-icon/react/icons/chevron-down';
import ChevronRightIcon from '@uplus-icon/react/icons/chevron-right';

export const iconProps = { size: 18, weight: 1.5, 'aria-hidden': true };
export const iconSm = { size: 16, weight: 1.5, 'aria-hidden': true };

export function Page({ children }) {
  return <main>{children}</main>;
}

export function ErrorNote({ error }) {
  if (!error) return null;
  return <p className="form-error" role="alert">{error}</p>;
}

export function IconButton({ label, children, className = '', ...props }) {
  return (
    <button type="button" className={`icon-button ${className}`.trim()} aria-label={label} title={label} {...props}>
      {children}
    </button>
  );
}

export function Disclosure({ className = '', summary, children, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <details open={open} className={`icon-disclosure ${className}`.trim()} onToggle={event => setOpen(event.currentTarget.open)}>
      <summary>
        {open ? <ChevronDownIcon {...iconSm} /> : <ChevronRightIcon {...iconSm} />}
        {summary}
      </summary>
      {children}
    </details>
  );
}

export function Dialog({ open, title, children, busy = false, onClose, className = '' }) {
  const ref = useRef(null);
  const titleId = useId();
  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    if (open) {
      if (!node.open) node.showModal();
      const focusable = node.querySelector('textarea, input:not([type="hidden"]), button:not([disabled])');
      focusable?.focus();
    } else if (node.open) {
      node.close();
    }
  }, [open]);
  return (
    <dialog
      ref={ref}
      className={`app-dialog ${className}`.trim()}
      aria-labelledby={title ? titleId : undefined}
      onCancel={(event) => { event.preventDefault(); if (!busy) onClose(); }}
      onClick={(event) => { if (event.target === event.currentTarget && !busy) onClose(); }}
    >
      {title ? <h2 id={titleId}>{title}</h2> : null}
      {children}
    </dialog>
  );
}

export function ConfirmDialog({ open, title, children, confirmLabel = '确认删除', busy = false, danger = true, onConfirm, onCancel }) {
  return (
    <Dialog open={open} title={title} busy={busy} onClose={onCancel}>
      {children ? <p className="hint">{children}</p> : null}
      <div className="actions">
        <button type="button" className={danger ? 'danger' : undefined} disabled={busy} onClick={onConfirm}>{busy ? (danger ? '正在删除…' : '处理中…') : confirmLabel}</button>
        <button type="button" className="secondary" disabled={busy} onClick={onCancel}>取消</button>
      </div>
    </Dialog>
  );
}
