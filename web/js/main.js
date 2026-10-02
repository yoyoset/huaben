// 入口:hash 路由 + service worker 注册。
import { h, mount } from './dom.js';
import './player.js';
import { cancelAllPolls } from './poll.js';
import { applyPrefs } from './reading_prefs.js';
import { openingView } from './views/opening.js';
import { readerView } from './views/reader.js';
import { shelfView } from './views/shelf.js';
import { statsView } from './views/stats.js';

const routes = [
  [/^#\/opening\/(\d+)$/, (m) => openingView(+m[1])],
  [/^#\/read\/(\d+)(?:\/(\d+))?$/, (m) => readerView(+m[1], m[2] ? +m[2] : undefined)],
  [/^#\/stats\/(\d+)$/, (m) => statsView(+m[1])],
  [/^#?\/?$/, () => shelfView()],
];

function route() {
  cancelAllPolls(); // 上一个页面的等待轮询随页面一起结束
  const hash = location.hash || '#/';
  for (const [re, view] of routes) {
    const m = hash.match(re);
    if (m) return view(m);
  }
  mount(h('div', { class: 'banner' }, '找不到这个页面'));
}

applyPrefs(); // 字号/行距在第一次渲染前就生效,避免跳动
window.addEventListener('hashchange', route);
route();

if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js').catch(() => { /* 不支持/非安全上下文:PWA 离线壳不可用,功能照常 */ });
}
