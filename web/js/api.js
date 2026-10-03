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
    throw Object.assign(new Error(detail), { status: res.status }); // status 供调用方区分(如 409 = 已在进行)
  }
  return res.json();
}

function rangeQuery(from, to) {
  const q = [from ? `from=${from}` : '', to ? `to=${to}` : ''].filter(Boolean).join('&');
  return q ? `?${q}` : '';
}

export const api = {
  profiles: () => call('GET', '/api/profiles'),
  createProfile: (name) => call('POST', '/api/profiles', { name }),
  books: (profileId) => call('GET', `/api/books?profile=${profileId}`),
  book: (id) => call('GET', `/api/books/${id}`),
  createBook: (title, profileId) => call('POST', '/api/books', { title, profile_id: profileId }),
  openingHistory: (id) => call('GET', `/api/books/${id}/opening`),
  say: (id, message) => call('POST', `/api/books/${id}/opening`, { message }),
  finalize: (id) => call('POST', `/api/books/${id}/finalize`),
  // from/to 可省:几千章的书只取需要的一段(整本目录每次都取会卡,服务端还要逐章查音频文件)
  chapters: (id, from, to) => call('GET', `/api/books/${id}/chapters${rangeQuery(from, to)}`),
  /** 当前章与前后各一章:算上一章/下一章、这章有没有音频只需要这些。 */
  around: (id, idx) => call('GET', `/api/books/${id}/chapters${rangeQuery(Math.max(1, idx - 1), idx + 1)}`),
  chapter: (id, idx) => call('GET', `/api/books/${id}/chapters/${idx}`),
  foreshadows: (id) => call('GET', `/api/books/${id}/foreshadows`),
  cast: (id) => call('GET', `/api/books/${id}/cast`),
  craftOptions: () => call('GET', '/api/craft/options'),
  expandWorld: (id) => call('POST', `/api/books/${id}/world/expand`),
  prepare: (id, count) => call('POST', `/api/books/${id}/prepare`, { count }),
  prepStatus: (id) => call('GET', `/api/books/${id}/prepare`),
  craft: (id) => call('GET', `/api/books/${id}/craft`),
  saveCraft: (id, craft) => call('PUT', `/api/books/${id}/craft`, craft),
  stats: (id) => call('GET', `/api/books/${id}/stats`),
  spend: () => call('GET', '/api/spend'),
  settings: () => call('GET', '/api/settings'),
  saveSettings: (body) => call('PUT', '/api/settings', body),
  testSettings: () => call('POST', '/api/settings/test'),
  voiceStatus: () => call('GET', '/api/voice/status'),
  voiceFallback: (id) => call('POST', `/api/voice/fallback/${id}`),
  openChapter: (id, chapter) => call('PUT', `/api/books/${id}/progress`, { chapter }),
};
