// 章内收听位置:存在本机浏览器里,每本书只记最近在听的那一章。
// 为什么要记:手机会在后台杀掉 PWA(iOS 尤其常见),播放位置原本只在内存里,重开后整章从头。
// 为什么只存本机:要解决的是"同一台设备重开后接着听";跨设备续听要每几秒写一次服务器,先不做。
// localStorage 可能不可用(隐私模式等):读写都包 try/catch,不可用时只是不记忆。
const key = (bookId) => `huaben.listen.${bookId}`;

export function loadPos(bookId) {
  try { return JSON.parse(localStorage.getItem(key(bookId)) || 'null'); } catch { return null; }
}

export function savePos(bookId, idx, t) {
  try { localStorage.setItem(key(bookId), JSON.stringify({ idx, t: Math.floor(t) })); } catch { /* 不记忆即可 */ }
}

export function clearPos(bookId) {
  try { localStorage.removeItem(key(bookId)); } catch { /* 同上 */ }
}
