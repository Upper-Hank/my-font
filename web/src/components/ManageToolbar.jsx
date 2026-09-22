import { useEffect, useRef } from 'react';
import ControlHorizonIcon from '@uplus-icon/react/icons/control-horizon';
import { iconSm } from '../ui.jsx';

export default function ManageToolbar({ managing, onEnter, onLeave, count, total, onSelectAll, onClear, busy = false, children }) {
  const toolbar = useRef(null);
  useEffect(() => {
    if (!managing) return;
    const onKey = event => {
      if (event.key !== 'Escape' || event.defaultPrevented || busy || document.querySelector('dialog[open]')) return;
      onLeave();
    };
    // Only one list owns the floating selection bar at a time.
    const onOtherSelection = event => {
      if (busy) event.preventDefault();
      else onLeave();
    };
    const updateSpace = () => document.body.style.setProperty('--selection-bar-height', `${toolbar.current?.offsetHeight || 0}px`);
    const observer = new ResizeObserver(updateSpace);
    observer.observe(toolbar.current);
    updateSpace();
    window.addEventListener('keydown', onKey);
    window.addEventListener('start-batch-selection', onOtherSelection);
    return () => {
      observer.disconnect();
      document.body.style.removeProperty('--selection-bar-height');
      window.removeEventListener('keydown', onKey);
      window.removeEventListener('start-batch-selection', onOtherSelection);
    };
  }, [managing, onLeave, busy]);

  function enter() {
    if (window.dispatchEvent(new Event('start-batch-selection', { cancelable: true }))) onEnter();
  }
  return <>
    <button type="button" className="batch-select-toggle with-icon" disabled={busy || (!managing && !total)} aria-pressed={managing} onClick={managing ? onLeave : enter}>
      <ControlHorizonIcon {...iconSm} />{managing ? '退出管理' : '管理'}
    </button>
    {managing && <div ref={toolbar} className="manage-toolbar" role="toolbar" aria-label="批量操作" aria-busy={busy}>
      <span className="hint" role="status">已选 {count} 项</span>
      <button type="button" disabled={busy || !total} onClick={onSelectAll}>全选</button>
      <button type="button" disabled={busy || count === 0} onClick={onClear}>清空</button>
      {children}
      <button type="button" disabled={busy} onClick={onLeave}>完成</button>
    </div>}
  </>;
}
