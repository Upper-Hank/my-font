import { memo, useMemo } from 'react';
import PlusIcon from '@uplus-icon/react/icons/plus';
import { iconSm } from '../ui.jsx';
import { geometry } from '../lib/template-canvas.js';
const code = char => `U+${char.codePointAt(0).toString(16).toUpperCase().padStart(4, '0')}`;

export default memo(function CanvasFrame({ generic = false, page, pageIndex, left, selectedPage, guides, selected, hand, typing, caret, events }) {
  const geo = geometry(page);
  const occupied = useMemo(() => new Map(page.cells.map(c => [c.slot, c])), [page.cells]);
  return <section className={`studio-frame${selectedPage ? ' active' : ''}${guides ? ' guides' : ''}${typing ? ' typing' : ''}`} style={{ left, width: geo.width * 3, height: geo.height * 3 }} aria-label={generic ? '书写纸' : `页面 ${pageIndex + 1}`} onClick={e => { if (e.target === e.currentTarget) events.current.choosePage(page.id, e); }}>
              <button className="studio-frame-label" onClick={e => events.current.choosePage(page.id, e)}>{generic ? '书写纸' : `页面 ${String(pageIndex + 1).padStart(2, '0')}`}<span>{geo.width} × {geo.height} mm</span></button>
              <div className="studio-safe-area" style={{ left:geo.guide.x * 3, top:geo.guide.y * 3, width:geo.guide.w * 3, height:geo.guide.h * 3 }} />
              {geo.slots.map((point, slot) => {
                const block = generic ? null : occupied.get(slot), isSelected = block && selected.has(block.id);
                const isCaret = typing && caret?.pageId === page.id && caret.slot === slot;
                return <button key={slot} className={`studio-slot${block ? ' filled' : ''}${isSelected ? ' selected' : ''}${isCaret ? ' caret' : ''}`} style={{ left:(point.x-2)*3, top:(point.y-2)*3, width:(page.size+4)*3, height:(page.size+4)*3 }}
                  aria-label={block ? `${block.char}，字格 ${slot+1}` : typing ? `空字格 ${slot+1}，从此处打字` : generic ? `字格 ${slot+1}` : `空字格 ${slot+1}，放入选中字块`} disabled={generic} aria-pressed={Boolean(isSelected)} draggable={Boolean(block) && !hand && !typing}
                  onClick={e => {
                    if (events.current.tool === 'type') { e.stopPropagation(); events.current.setCaret({ pageId: page.id, slot }); events.current.choosePage(page.id, e); return; }
                    if (block) events.current.pickBlock(block,e,page.id); else if (events.current.selection.length) events.current.move(events.current.selection,page.id,slot); else events.current.choosePage(page.id,e);
                  }}
                  onDoubleClick={() => { if (block && events.current.tool !== 'type') { events.current.setEditing(block.id); events.current.setEditText(block.char); } }}
                  onDragStart={e => block && events.current.startDrag(block,e)} onDragEnd={() => { events.current.drag.current = null; events.current.highlightDrop(null); }}
                  onDragOver={e => { if (events.current.drag.current) { e.preventDefault(); events.current.highlightDrop(e.currentTarget); } }}
                  onDrop={e => { e.preventDefault(); e.stopPropagation(); if (events.current.drag.current) events.current.move(events.current.drag.current,page.id,slot); }}>
                  <small>{String(slot+1).padStart(2,'0')}</small>{block ? <strong>{block.char}</strong> : typing ? <span className="studio-slot-caret" aria-hidden="true" /> : generic ? null : <span><PlusIcon {...iconSm} size={14} /></span>}{block ? <em>{code(block.char)}</em> : null}
                </button>;
              })}
            </section>;

});
