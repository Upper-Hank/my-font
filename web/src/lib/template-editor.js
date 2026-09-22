export function parseCells(text) {
  const parts = String(text || '').replace(/^\uFEFF/, '').split(/\s+/).filter(Boolean);
  const chars = parts.flatMap(part => {
    if (!part.toUpperCase().startsWith('U+')) return [...part];
    if (!/^U\+[0-9a-f]{4,6}$/i.test(part) || parseInt(part.slice(2), 16) > 0x10ffff) throw new Error('Unicode 格式无效，请用 U+5B57，编码之间用空格分隔。');
    return [String.fromCodePoint(parseInt(part.slice(2), 16))];
  });
  if (chars.some(c => /[\p{C}\p{M}]/u.test(c))) throw new Error('暂不支持控制字符、组合标记或未分配字符。');
  return chars;
}

// Destination is an insertion boundary in the original list, including its end.
export function moveCells(cells, indices, destination) {
  const selected = new Set(indices);
  const moving = cells.filter((_, i) => selected.has(i));
  const rest = cells.filter((_, i) => !selected.has(i));
  const at = destination - indices.filter(i => i < destination).length;
  return { cells: [...rest.slice(0, at), ...moving, ...rest.slice(at)],
    selection: moving.map((_, i) => at + i) };
}
