// 只缓存"应用壳"(页面/脚本/样式/图标),让 PWA 可安装、打开快。
// 刻意不缓存 /api/*(含音频):内容随连载变化,缓存会让读者看到过期状态。
const VERSION = 'huaben-shell-v5';
const SHELL = ['/', '/css/app.css', '/js/main.js', '/js/api.js', '/js/dom.js', '/js/logic.js', '/js/player.js',
  '/js/poll.js', '/js/reading_prefs.js', '/js/network.js', '/js/listen_pos.js',
  '/js/views/shelf.js', '/js/views/stats.js', '/js/views/opening.js', '/js/views/reader.js', '/manifest.webmanifest', '/icons/icon-192.png'];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(VERSION).then((c) => c.addAll(SHELL)));
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== VERSION).map((k) => caches.delete(k)))));
  self.clients.claim();
});

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET' || url.pathname.startsWith('/api/')) return; // 交给网络
  // 壳资源:网络优先,断网回退缓存(改了前端代码刷新就能生效)
  e.respondWith(fetch(e.request).then((r) => {
    const copy = r.clone();
    caches.open(VERSION).then((c) => c.put(e.request, copy));
    return r;
  }).catch(() => caches.match(e.request)));
});
