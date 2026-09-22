import { useState } from 'react';
import TrashIcon from '@uplus-icon/react/icons/trash';
import { postJson } from '../api.js';
import { ConfirmDialog, iconSm } from '../ui.jsx';

const COPY = {
  template: '删除这个模板。已经切出来的字形还在字形库里。',
  'template-trash': '删除回收站里的模板文件。已经切出来的字形还在。',
  preview: '删除这些照片和校正文件。',
  'preview-trash': '删除回收站里的未完成任务。',
  run: '删除这次转换的原照片、处理文件和未加入的结果，无法恢复。已加入字符库的字形保留。',
  completed: '删除全部已完成转换的原照片和处理文件。字形库里的字还在。',
};

export default function HistoryCleanupButton({ kind, id, label = '删除', onComplete, onError, iconOnly = false }) {
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  async function cleanup() {
    setBusy(true);
    try { await postJson('/history/cleanup', { kind, id }); await onComplete(); setConfirming(false); }
    catch (e) { onError(e.message); }
    finally { setBusy(false); }
  }
  return <>
    <button type="button" className={iconOnly ? 'icon-button danger' : 'danger with-icon'} aria-label={iconOnly ? label : undefined} title={iconOnly ? label : undefined} onClick={() => setConfirming(true)}><TrashIcon {...iconSm} />{iconOnly ? null : label}</button>
    <ConfirmDialog open={confirming} title={`${label}？`} confirmLabel="确认删除" busy={busy} onConfirm={cleanup} onCancel={() => { if (!busy) setConfirming(false); }}>
      {COPY[kind] || '确认删除这些文件？'}
    </ConfirmDialog>
  </>;
}
