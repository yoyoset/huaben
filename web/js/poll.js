// 有上限的轮询。换页面时 main.js 调 cancelAllPolls(),不会在别的页面背后一直打请求。
import { pollDelay } from './logic.js';

const active = new Set();

/**
 * 反复调用 check(),直到它返回 true(完成)或次数用尽(调用 onGiveUp)。
 * check 抛错(网络抖动)当作"还没好",继续等。返回取消函数。
 */
export function poll(check, { onGiveUp } = {}) {
  let attempt = 0;
  let timer = null;
  const job = { cancel: () => { clearTimeout(timer); active.delete(job); } };
  const schedule = () => {
    const sec = pollDelay(attempt++);
    if (sec == null) { job.cancel(); onGiveUp?.(); return; }
    timer = setTimeout(async () => {
      let done = false;
      try { done = await check(); } catch { /* 网络抖动:继续等 */ }
      if (!active.has(job)) return;  // 等待期间被取消了(用户换了页面)
      if (done) job.cancel(); else schedule();
    }, sec * 1000);
  };
  active.add(job);
  schedule();
  return job.cancel;
}

export function cancelAllPolls() {
  [...active].forEach((j) => j.cancel());
}
