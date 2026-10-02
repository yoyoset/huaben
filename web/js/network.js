// 断网/恢复提示。断网时顶部常驻一条提示(而不是让每个按钮各自报"连不上");
// 恢复后提示消失,并刷新当前页面,把断网期间错过的状态补拉回来。
const banner = document.getElementById('net-banner');
export const OFFLINE_TEXT = '网络已断开:已加载的内容可以继续读,恢复后会自动刷新。';

function show(offline) {
  banner.hidden = !offline;
  banner.textContent = offline ? OFFLINE_TEXT : '';
}

export function watchNetwork(onBack) {
  window.addEventListener('offline', () => show(true));
  window.addEventListener('online', () => { show(false); onBack(); });
  show(navigator.onLine === false);
}
