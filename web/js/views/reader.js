// 阅读:最近读到的章(或指定章)、上/下章、"听这一章";目录是单独一页(views/toc.js)。
// 等待态(要看的章还在写 / 下一章还在写 / 语音还在准备)自动轮询刷新,不用读者手动刷新。
import { api } from '../api.js';
import { fill, h, mount, setTopTitle } from '../dom.js';
import { bookHome, chapterAvailability, nextChapter, paragraphs, prevChapter } from '../logic.js';
import { play } from '../player.js';
import { poll } from '../poll.js';
import { prefsToolbar } from '../reading_prefs.js';
import { voiceNoteEl } from './voice_note.js';

const go = (bookId, idx) => { location.hash = `#/read/${bookId}/${idx}`; };
const errorBanner = (book) => [
  book.gen_error ? h('div', { class: 'banner', role: 'alert' }, `后台生成遇到问题:${book.gen_error}`) : null,
  // 配音问题不影响阅读,用较轻的提示,不打断读屏
  book.audio_error ? h('div', { class: 'note' }, `🎧 ${book.audio_error}`) : null,
];

export async function readerView(bookId, idxParam) {
  const box = h('div', {}, h('p', { class: 'muted' }, '加载中…'));
  mount(box);
  try {
    // 配音状态取不到不影响阅读(只是少一条提示)
    const [book, chapters, voice] = await Promise.all([api.book(bookId), api.around(bookId, idxParam ?? 1), api.voiceStatus().catch(() => null)]);
    setTopTitle(book.title);
    // 开书阶段的书不会自己开始写:不要在这里空等"第一章",直接回到开书对话
    if (book.status === 'drafting') { location.replace(bookHome(book)); return; }
    // 没指定章:接着上次打开的那章(last_opened;0 表示还没读过 → 第 1 章)
    const idx = idxParam ?? Math.max(1, book.last_opened);
    // 先按目录判断这章在不在,而不是请求了再看 404:深链/书签可能指向还没写好的章,要等而不是报错
    // 没指定章时续读位置要等拿到 book 才知道:补取一次它前后的章
    const near = idxParam == null && idx !== 1 ? await api.around(bookId, idx) : chapters;
    const state = chapterAvailability(near, idx, book.generating, book.ready_chapters);
    if (state !== 'ready') return notYet(box, book, bookId, idxParam, idx, state);
    const ch = await api.chapter(bookId, idx);
    api.openChapter(bookId, idx).catch(() => {});
    const prev = prevChapter(near, idx);
    const next = nextChapter(near, idx);
    const note = h('p', { class: 'muted' }); // 底部一行提示位,供 listen 回显
    const audioHint = h('span', { class: 'muted' }, ch.audio_url ? '' : '语音还在准备');
    const nextBtn = h('button', { class: 'primary', disabled: !next, onclick: () => go(bookId, next.idx) },
      next ? '下一章 →' : '下一章还在写');
    fill(box,
      errorBanner(book),
      voiceNoteEl(book, voice),
      h('div', { class: 'row', style: 'justify-content:space-between' },
        h('div', { class: 'row' }, tocLink(bookId, book), h('a', { class: 'btn', href: `#/stats/${bookId}`, 'aria-label': '本书运行统计' }, '📊 统计')),
        prefsToolbar()),
      h('h1', { class: 'chapter-title' }, `第${idx}章 ${ch.title}`),
      h('div', { class: 'row' },
        h('button', { class: 'primary', onclick: () => listen(bookId, idx, book.title, note) }, '🎧 听这一章'),
        audioHint),
      h('div', { class: 'chapter-body' }, paragraphs(ch.body).map((p) => h('p', {}, p))),
      h('div', { class: 'chapter-nav' },
        h('button', { disabled: !prev, onclick: () => go(bookId, prev.idx) }, '← 上一章'), nextBtn),
      tocLink(bookId, book),
      note,
      h('button', { onclick: () => window.scrollTo({ top: 0, behavior: 'smooth' }) }, '↑ 回到顶部'),
    );
    if (!next || !ch.audio_url) watchPending(bookId, idx, nextBtn, audioHint, !next, !ch.audio_url);
  } catch (e) {
    fill(box, h('div', { class: 'banner', role: 'alert' }, e.message));
  }
}

/** 下一章/本章语音还没好:轮询目录,好了就就地更新按钮和提示,不重绘正文(不打断阅读位置)。 */
function watchPending(bookId, idx, nextBtn, audioHint, needNext, needAudio) {
  poll(async () => {
    const chapters = await api.around(bookId, idx);
    const next = nextChapter(chapters, idx);
    if (needNext && next) {
      needNext = false;
      nextBtn.disabled = false;
      nextBtn.textContent = '下一章 →';
      nextBtn.onclick = () => go(bookId, next.idx);
    }
    if (needAudio && chapters.find((c) => c.idx === idx)?.has_audio) {
      needAudio = false;
      audioHint.textContent = '';
    }
    return !needNext && !needAudio;
  }, { onGiveUp: () => { if (needNext) nextBtn.textContent = '下一章还在写(稍后再来看看)'; } });
}

const tocLink = (bookId, book) => h('a', { class: 'btn', href: `#/toc/${bookId}` }, `📖 目录(${book.ready_chapters} 章)`);

async function listen(bookId, idx, bookTitle, note) {
  try {
    const ok = await play(bookId, idx, bookTitle);
    note.textContent = ok ? '' : '这一章的语音还没准备好,先读文字吧。';
  } catch (e) {
    note.textContent = e.message;
  }
}

/**
 * 要看的章还不能看。只有"正在写"的那一章值得自动等;"还早"的章读者不往下读就不会写到,空等只会白白轮询。
 * 重绘时沿用原来的 idxParam:没指定章号的入口(书架点进来)写好后仍走"接着上次读"的逻辑。
 */
function notYet(box, book, bookId, idxParam, idx, state) {
  const latest = book.ready_chapters;
  const label = idx === 1 ? '第一章' : `第${idx}章`;
  const text = {
    // 后台已报错时不说"通常一两分钟"——那会让读者以为只要再等等
    writing: book.gen_error ? `${label}暂时写不了(原因见上),问题解决后会自动打开。`
      : `${label}还在写,通常一两分钟,写好会自动打开。`,
    later: `第${idx}章还没写到。后台只比你的阅读进度多备几章,往下读就会接着写。`,
    missing: `没有第${idx}章。`,
  }[state];
  const hint = h('p', { class: 'muted' }, text);
  let stopPoll = () => {};  // 手动刷新要先停掉本页的轮询,否则旧轮询和新页面的轮询会叠在一起
  const links = state === 'writing'
    ? [h('button', { onclick: () => { stopPoll(); readerView(bookId, idxParam); } }, '立即刷新')]
    : [latest ? h('a', { class: 'btn primary', href: `#/read/${bookId}/${latest}` }, `去最新的第${latest}章`) : null,
      h('a', { class: 'btn', href: `#/read/${bookId}` }, '回到上次读的地方')];
  fill(box, h('h2', {}, book.title), errorBanner(book), hint, h('div', { class: 'row' }, links));
  if (state !== 'writing') return;
  stopPoll = poll(async () => {
    if (!(await api.around(bookId, idx)).some((c) => c.idx === idx)) return false;
    readerView(bookId, idxParam);
    return true;
  }, { onGiveUp: () => { hint.textContent = '等得有点久了,后台可能遇到了问题。可以稍后点"立即刷新"再看。'; } });
}
