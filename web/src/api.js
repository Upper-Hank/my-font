async function read(response) {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || '操作未完成，请重试。');
  return data;
}

export function getJson(url) {
  return fetch(url, { headers: { Accept: 'application/json' } }).then(read);
}

export function postJson(url, body) {
  return fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify(body),
  }).then(read);
}

export function postForm(url, form) {
  return fetch(url, { method: 'POST', body: form, headers: { Accept: 'application/json' } }).then(read);
}
