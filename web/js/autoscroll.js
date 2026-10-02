// 自动滚屏 + 连续阅读(2026-10-02 用户:读这一章时自动往下走,读完接着下一章)。
// 滚到章末 → 交给阅读页翻到下一章(下一章还在写就等它);翻过去后接着滚,直到读者暂停或离开阅读页。
// 跨章靠 sessionStorage 记"正在自动读":换章是整页重绘,模块状态留不住;离开阅读页就清掉,下次进来不会自己动。
import { h } from './dom.js';
import { SCROLL_SPEEDS, atPageEnd, stepScrollSpeed } from './logic.js';
import { load, save } from './reading_prefs.js';

const FLAG = 'huaben.autoscroll';
const flag = {
  get: () => { try { return sessionStorage.getItem(FLAG) === '1'; } catch { return false; } },
  set: (on) => { try { on ? sessionStorage.setItem(FLAG, '1') : sessionStorage.removeItem(FLAG); } catch { /* 不可用:只是不跨章 */ } },
};

let current = null; // 当前页面的控制器 { pause }:全局监听只登记一次,永远作用在当前这一页上

window.addEventListener('hashchange', () => { if (!location.hash.startsWith('#/read/')) flag.set(false); });
// 读者自己动手(滚轮/拖动)= 想自己看:暂停,别跟他抢。用 touchmove 而不是 touchstart:
// 点一下正文是"暂停/继续",touchstart 会先把它暂停、紧接着的 click 又把它继续。
const manual = () => current?.pause();
window.addEventListener('wheel', manual, { passive: true });
window.addEventListener('touchmove', manual, { passive: true });

/**
 * 阅读页工具条上的一组按钮:▶ 自动滚屏 / 慢 / 快。
 * body:正文元素——点正文 = 暂停/继续(用过自动滚屏之后才生效,免得读者随手一点它自己动起来);
 *       它离开页面时滚动自动停止。
 * onEnd():滚到章末时调用,由阅读页决定翻到下一章还是等下一章写好。
 */
export function autoScrollControls(body, onEnd) {
  let speed = load().scrollSpeed ?? 1;
  let run = null;   // 正在滚:{ raf, last, pos, lock }
  let used = false; // 这一页用过自动滚屏
  const toggle = h('button', { class: 'primary', 'aria-pressed': 'false' }, '▶ 自动滚屏');
  const speedLabel = h('span', { class: 'muted' });
  const showSpeed = () => { speedLabel.textContent = `速度 ${speed + 1}/${SCROLL_SPEEDS.length}`; };
  const setSpeed = (dir) => { speed = stepScrollSpeed(speed, dir); save({ ...load(), scrollSpeed: speed }); showSpeed(); };

  const halt = () => {
    if (!run) return;
    cancelAnimationFrame(run.raf);
    run.lock?.release().catch(() => {});
    run = null;
    toggle.textContent = '▶ 自动滚屏';
    toggle.setAttribute('aria-pressed', 'false');
  };
  const pause = () => { if (run) { halt(); flag.set(false); } };
  const start = async () => {
    halt();
    used = true;
    flag.set(true);
    toggle.textContent = '⏸ 暂停';
    toggle.setAttribute('aria-pressed', 'true');
    const r = { raf: 0, last: 0, pos: window.scrollY, lock: null };
    run = r;
    const tick = (t) => {
      if (run !== r) return;
      if (!body.isConnected) return halt(); // 换章/离开:本页滚动结束,要不要接着滚由下一页按 FLAG 决定
      const dt = r.last ? Math.min(t - r.last, 100) / 1000 : 0; // 切到后台再回来 dt 很大:封顶,免得一下跳一屏
      r.last = t;
      r.pos += SCROLL_SPEEDS[speed] * dt;
      window.scrollTo(0, r.pos);
      if (atPageEnd(window.scrollY, window.innerHeight, document.documentElement.scrollHeight)) {
        halt(); // 保留 FLAG:下一章打开后接着滚
        return onEnd();
      }
      r.raf = requestAnimationFrame(tick);
    };
    r.raf = requestAnimationFrame(tick);
    try { r.lock = await navigator.wakeLock?.request('screen'); } catch { /* 不支持/被拒:屏幕可能自己熄灭,滚动照常 */ }
  };

  current = { pause };
  showSpeed();
  toggle.onclick = () => (run ? pause() : start());
  body.addEventListener('click', () => { if (run) pause(); else if (used) start(); });
  // 上一章读完自动翻过来的:稍停让读者看清标题,再接着滚
  if (flag.get()) setTimeout(() => { if (body.isConnected && !run) start(); }, 1500);

  return h('div', { class: 'row', role: 'group', 'aria-label': '自动滚屏' }, toggle,
    h('button', { 'aria-label': '慢一点', onclick: () => setSpeed(-1) }, '慢'),
    h('button', { 'aria-label': '快一点', onclick: () => setSpeed(+1) }, '快'), speedLabel);
}
