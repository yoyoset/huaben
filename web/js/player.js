// 全局播放器(单例)。设计要点:
//  - 始终复用同一个 <audio>,换章只改 src。iOS 锁屏后,新建的 audio 元素不允许自动播放,复用的才行(待真机验证)。
//  - Media Session 提供锁屏/耳机控制与元数据。
//  - 一章播完按 logic.afterEnded 决定:接下一章 / 停(睡眠定时)/ 等(后台还在生成)。
import { api } from './api.js';
import { afterEnded, nextChapter, nextRate, nextSleepOption, prevChapter, SLEEP_OPTIONS } from './logic.js';

const audio = document.getElementById('audio');
const bar = document.getElementById('player');
const $ = (id) => document.getElementById(id);

const st = { bookId: null, bookTitle: '', idx: null, title: '', sleepIdx: 0, sleepTimer: null, waitTimer: null };
const listeners = new Set();
export const onChange = (fn) => listeners.add(fn);
const emit = () => listeners.forEach((fn) => fn({ ...st, playing: !audio.paused }));

function status(text) { $('player-status').textContent = text || ''; }

function updateMediaSession() {
  if (!('mediaSession' in navigator)) return;
  navigator.mediaSession.metadata = new MediaMetadata({
    title: `第${st.idx}章 ${st.title}`, artist: st.bookTitle, album: '话本',
    artwork: [{ src: '/icons/icon-512.png', sizes: '512x512', type: 'image/png' }],
  });
}

function bindMediaSession() {
  if (!('mediaSession' in navigator)) return;
  const set = (a, fn) => { try { navigator.mediaSession.setActionHandler(a, fn); } catch { /* 部分浏览器不支持某动作 */ } };
  set('play', () => audio.play());
  set('pause', () => audio.pause());
  set('previoustrack', () => step(-1));
  set('nexttrack', () => step(1));
  set('seekbackward', () => { audio.currentTime = Math.max(0, audio.currentTime - 15); });
  set('seekforward', () => { audio.currentTime = Math.min(audio.duration || 0, audio.currentTime + 15); });
  set('seekto', (d) => { audio.currentTime = d.seekTime; });
}

function syncPosition() {
  if (!('mediaSession' in navigator) || !isFinite(audio.duration)) return;
  try {
    navigator.mediaSession.setPositionState({ duration: audio.duration, playbackRate: audio.playbackRate, position: audio.currentTime });
  } catch { /* 时长未就绪时会抛,忽略 */ }
}

/** 播放某书某章。返回 false 表示这章还没有音频(调用方可提示"只能读")。 */
export async function play(bookId, idx, bookTitle) {
  clearTimeout(st.waitTimer);
  const ch = await api.chapter(bookId, idx);
  if (!ch.audio_url) return false;
  Object.assign(st, { bookId, idx, bookTitle: bookTitle ?? st.bookTitle, title: ch.title });
  audio.src = ch.audio_url;
  audio.playbackRate = parseFloat($('btn-rate').dataset.rate || '1');
  bar.hidden = false;
  $('player-title').textContent = `第${idx}章 ${ch.title}`;
  status('');
  updateMediaSession();
  await audio.play();
  api.openChapter(bookId, idx).catch(() => {}); // 进度上报失败不影响播放
  emit();
  return true;
}

async function step(dir) {
  if (st.bookId == null) return;
  const chapters = await api.chapters(st.bookId);
  const target = dir > 0 ? nextChapter(chapters, st.idx) : prevChapter(chapters, st.idx);
  if (target?.has_audio) await play(st.bookId, target.idx);
  else status(dir > 0 ? '下一章还在准备' : '已经是第一章');
}

/** 下一章还没好:每 20 秒看一次,最多等 10 分钟,好了自动接着播。 */
function waitForNext(tries = 0) {
  status('下一章还在准备,好了自动接着播…');
  if (tries >= 30) return status('下一章迟迟没好,稍后手动点 ⏭');
  st.waitTimer = setTimeout(async () => {
    try {
      const next = nextChapter(await api.chapters(st.bookId), st.idx);
      if (next?.has_audio) return play(st.bookId, next.idx);
    } catch { /* 网络抖动:继续等 */ }
    waitForNext(tries + 1);
  }, 20000);
}

audio.addEventListener('ended', async () => {
  const opt = SLEEP_OPTIONS[st.sleepIdx];
  let next = null;
  try { next = nextChapter(await api.chapters(st.bookId), st.idx); } catch { /* 取不到当作没有 */ }
  const action = afterEnded({ stopAtChapterEnd: opt.endOfChapter, next });
  if (action === 'next') await play(st.bookId, next.idx);
  else if (action === 'wait') waitForNext();
  else { status('睡眠定时:已停止'); setSleep(0); }
  emit();
});
audio.addEventListener('play', () => { setToggle('⏸', '暂停'); emit(); });
audio.addEventListener('pause', () => { setToggle('▶', '播放'); emit(); });
// 图标按钮的可读名要随状态变(读屏念的是 aria-label,不是 ▶/⏸ 这种符号)
function setToggle(icon, label) { $('btn-toggle').textContent = icon; $('btn-toggle').setAttribute('aria-label', label); }
audio.addEventListener('timeupdate', syncPosition);
audio.addEventListener('error', () => status('音频加载失败,稍后重试'));

function setSleep(idx) {
  st.sleepIdx = idx;
  clearTimeout(st.sleepTimer);
  const opt = SLEEP_OPTIONS[idx];
  $('btn-sleep').textContent = opt.minutes || opt.endOfChapter ? `🌙 ${opt.label}` : '🌙';
  $('btn-sleep').setAttribute('aria-label', `睡眠定时:${opt.label}`);
  if (opt.minutes) st.sleepTimer = setTimeout(() => { audio.pause(); status('睡眠定时:已暂停'); setSleep(0); }, opt.minutes * 60000);
}

$('btn-toggle').addEventListener('click', () => (audio.paused ? audio.play() : audio.pause()));
$('btn-prev').addEventListener('click', () => step(-1));
$('btn-next').addEventListener('click', () => step(1));
$('btn-sleep').addEventListener('click', () => setSleep(nextSleepOption(st.sleepIdx)));
$('btn-rate').addEventListener('click', () => {
  const r = nextRate(audio.playbackRate);
  audio.playbackRate = r;
  $('btn-rate').dataset.rate = r;
  $('btn-rate').textContent = `${r.toFixed(2).replace(/0$/, '')}×`;
  $('btn-rate').setAttribute('aria-label', `语速 ${r} 倍`);
});
bindMediaSession();
