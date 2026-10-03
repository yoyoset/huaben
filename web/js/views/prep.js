// 出门前预备 N 章(2026-10-03 用户:跑步前备好 10 章、20 章离线听)。网页这里只负责"开始备"和看进度;
// 把 MP3 下到手机本地由安卓 App 做(网页走 http,浏览器不允许离线缓存)。
import { api } from '../api.js';
import { h } from '../dom.js';
import { poll } from '../poll.js';

const text = (v) => (v.done
  ? `🏃 第 ${v.start}~${v.end} 章已备好(正文 + 音频),可以在 App 里下载离线听`
  : `🏃 正在备第 ${v.start}~${v.end} 章:正文 ${v.text_ready}/${v.total},音频 ${v.audio_ready}/${v.total}`
    + (v.audio_ready < v.text_ready ? '(音频要电脑开着配音程序)' : ''));

export function prepBox(bookId) {
  const status = h('span', { class: 'muted' });
  const watch = () => poll(async () => {
    const v = await api.prepStatus(bookId);
    status.textContent = v.active ? text(v) : '';
    return !v.active || v.done;
  });
  const start = (n) => async () => {
    status.textContent = '开始准备…';
    try { status.textContent = text(await api.prepare(bookId, n)); watch(); } catch (e) { status.textContent = e.message; }
  };
  api.prepStatus(bookId).then((v) => { if (v.active) { status.textContent = text(v); if (!v.done) watch(); } }).catch(() => {});
  return h('div', { class: 'row', style: 'margin:6px 0' },
    h('span', {}, '出门听:'),
    h('button', { onclick: start(10) }, '备 10 章'),
    h('button', { onclick: start(20) }, '备 20 章'),
    status);
}
