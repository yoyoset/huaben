// 后端接口封装。出错统一抛 Error(message = 后端给的人话 detail)。
async function call(method, path, body) {
  let res;
  try {
    res = await fetch(path, {
      method,
      headers: body ? { 'content-type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new Error('连不上服务,检查网络或 Tailscale 是否在线');
  }
  if (!res.ok) {
    let detail = `请求失败(${res.status})`;
    try {
      const j = await res.json();
      if (typeof j.detail === 'string') detail = j.detail;
    } catch { /* 非 JSON 响应,用默认文案 */ }
    throw new Error(detail);
  }
  return res.json();
}

export const api = {
  books: () => call('GET', '/api/books'),
  book: (id) => call('GET', `/api/books/${id}`),
  createBook: (title) => call('POST', '/api/books', { title }),
  openingHistory: (id) => call('GET', `/api/books/${id}/opening`),
  say: (id, message) => call('POST', `/api/books/${id}/opening`, { message }),
  finalize: (id) => call('POST', `/api/books/${id}/finalize`),
  chapters: (id) => call('GET', `/api/books/${id}/chapters`),
  chapter: (id, idx) => call('GET', `/api/books/${id}/chapters/${idx}`),
  setProgress: (id, readPos) => call('PUT', `/api/books/${id}/progress`, { read_pos: readPos }),
};
