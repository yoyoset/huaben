// 全局播放器(单例)。设计要点:
//  - 始终复用同一个 <audio>,换章只改 src。iOS 锁屏后,新建的 audio 元素不允许自动播放,复用的才行(待真机验证)。
//  - Media Session 提供锁屏/耳机控制与元数据。
//  - 一章播完按 logic.afterEnded 决定:接下一章 / 停(睡眠定时)/ 等(后台还在生成)。
import { api } from './api.js';
import { clearPos, loadPos, savePos } from './listen_pos.js';
import { afterEnded, fmtSeconds, nextChapter, nextRate, nextSleepOption, playFailure, prevChapter, resumeAt,
  SLEEP_OPTIONS } from './logic.js';

const audio = document.getElementById('audio');
const bar = document.getElementById('player');
const $ = (id) => document.getElementById(id);

const st = { bookId: null, bookTitle: '', idx: null, title: '', sleepIdx: 0, sleepTimer: null, waitTimer: null,
  resume: null, lastSaved: 0, reported: null };  // resume:本机记下的上次位置,元数据到了再决定要不要跳过去
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
  Object.assign(st, { bookId, idx, bookTitle: bookTitle ?? st.bookTitle, title: ch.title, resume: loadPos(bookId), lastSaved: 0 });
  audio.src = ch.audio_url;
  audio.playbackRate = parseFloat($('btn-rate').dataset.rate || '1');
  bar.hidden = false;
  $('player-title').textContent = `第${idx}章 ${ch.title}`;
  status('');
  updateMediaSession();
  try {
    await audio.play();
  } catch (e) {
    const kind = playFailure(e);
    if (kind === 'error') throw e;
    // 被拦:章已换好(src、标题、锁屏信息都是新章),读者点 ▶ 就从这里播;进度等真正开始播放时再上报
    if (kind === 'blocked') status(`点 ▶ 继续播放第${idx}章`);
  }
  emit();
  return true;
}

/** 播放器自己发起的换章(下一章/上一章/自动续播):没有调用方接错误,所以在这里显示。 */
function playFromPlayer(idx) {
  return play(st.bookId, idx).catch((e) => status(e.message));
}

async function step(dir) {
  if (st.bookId == null) return;
  let chapters;
  try { chapters = await api.chapters(st.bookId); } catch (e) { return status(e.message); }
  const target = dir > 0 ? nextChapter(chapters, st.idx) : prevChapter(chapters, st.idx);
  if (target?.has_audio) await playFromPlayer(target.idx);
  else status(dir > 0 ? '下一章还在准备' : '已经是第一章');
}

// 进度在"真正开始出声"时上报,而不是 play() 一调用就报:自动续播被浏览器拦下时,读者其实没听到这一章。
// 每章只报一次(暂停后继续不重复报)。上报失败不影响播放。
audio.addEventListener('playing', () => {
  const key = `${st.bookId}:${st.idx}`;
  if (st.bookId == null || st.reported === key) return;
  st.reported = key;
  api.openChapter(st.bookId, st.idx).catch(() => {});
});

/** 下一章还没好:每 20 秒看一次,最多等 10 分钟,好了自动接着播。 */
function waitForNext(tries = 0) {
  status('下一章还在准备,好了自动接着播…');
  if (tries >= 30) return status('下一章迟迟没好,稍后手动点 ⏭');
  st.waitTimer = setTimeout(async () => {
    try {
      const next = nextChapter(await api.chapters(st.bookId), st.idx);
      if (next?.has_audio) return playFromPlayer(next.idx);
    } catch { /* 网络抖动:继续等 */ }
    waitForNext(tries + 1);
  }, 20000);
}

// —— 章内位置:元数据到了才知道时长,这时再决定跳不跳;播放中每 5 秒、暂停/离开页面时记一次;听完就清掉
audio.addEventListener('loadedmetadata', () => {
  const t = resumeAt(st.resume, st.idx, audio.duration);
  st.resume = null;
  if (t <= 0) return;
  audio.currentTime = t;
  if (!audio.paused) status(`接着上次的位置(${fmtSeconds(t)})`); // 被拦下时保留"点 ▶ 继续"的提示
});
function rememberPos(force = false) {
  if (st.bookId == null || !audio.currentTime) return;
  if (!force && Math.abs(audio.currentTime - st.lastSaved) < 5) return;
  savePos(st.bookId, st.idx, audio.currentTime);
  st.lastSaved = audio.currentTime;
}
audio.addEventListener('timeupdate', () => rememberPos());
audio.addEventListener('pause', () => { if (!audio.ended) rememberPos(true); });
window.addEventListener('pagehide', () => rememberPos(true));

audio.addEventListener('ended', async () => {
  if (st.bookId != null) clearPos(st.bookId);
  const opt = SLEEP_OPTIONS[st.sleepIdx];
  let next = null;
  try { next = nextChapter(await api.chapters(st.bookId), st.idx); } catch { /* 取不到当作没有 */ }
  const action = afterEnded({ stopAtChapterEnd: opt.endOfChapter, next });
  if (action === 'next') await playFromPlayer(next.idx);
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
