// 阅读:最近读到的章(或指定章)、目录、上/下章、"听这一章"。
// 等待态(第一章还没写好 / 下一章还在写 / 语音还在准备)自动轮询刷新,不用读者手动刷新。
import { api } from '../api.js';
import { fill, h, mount, setTopTitle } from '../dom.js';
import { chapterMark, nextChapter, paragraphs, prevChapter } from '../logic.js';
import { play } from '../player.js';
import { poll } from '../poll.js';
import { prefsToolbar } from '../reading_prefs.js';

const go = (bookId, idx) => { location.hash = `#/read/${bookId}/${idx}`; };
const errorBanner = (book) => (book.gen_error ? h('div', { class: 'banner' }, `后台生成遇到问题:${book.gen_error}`) : null);

export async function readerView(bookId, idxParam) {
  const box = h('div', {}, h('p', { class: 'muted' }, '加载中…'));
  mount(box);
  try {
    const [book, chapters] = await Promise.all([api.book(bookId), api.chapters(bookId)]);
    setTopTitle(book.title);
    if (!chapters.length) return waiting(box, book, bookId);
    // 没指定章:接着上次打开的那章(last_opened;0 表示还没读过 → 第 1 章)
    const idx = idxParam ?? Math.max(1, book.last_opened);
    const ch = await api.chapter(bookId, idx);
    api.openChapter(bookId, idx).catch(() => {});
    const prev = prevChapter(chapters, idx);
    const next = nextChapter(chapters, idx);
    const note = h('p', { class: 'muted' }); // 底部一行提示位,供 listen 回显
    const audioHint = h('span', { class: 'muted' }, ch.audio_url ? '' : '语音还在准备');
    const nextBtn = h('button', { class: 'primary', disabled: !next, onclick: () => go(bookId, next.idx) },
      next ? '下一章 →' : '下一章还在写');
    fill(box,
      errorBanner(book),
      prefsToolbar(),
      h('h1', { class: 'chapter-title' }, `第${idx}章 ${ch.title}`),
      h('div', { class: 'row' },
        h('button', { class: 'primary', onclick: () => listen(bookId, idx, book.title, note) }, '🎧 听这一章'),
        audioHint),
      h('div', { class: 'chapter-body' }, paragraphs(ch.body).map((p) => h('p', {}, p))),
      h('div', { class: 'chapter-nav' },
        h('button', { disabled: !prev, onclick: () => go(bookId, prev.idx) }, '← 上一章'), nextBtn),
      toc(bookId, chapters, idx, Math.max(book.read_pos, idx)),
      note,
      h('button', { onclick: () => window.scrollTo({ top: 0, behavior: 'smooth' }) }, '↑ 回到顶部'),
    );
    if (!next || !ch.audio_url) watchPending(bookId, idx, nextBtn, audioHint, !next, !ch.audio_url);
  } catch (e) {
    fill(box, h('div', { class: 'banner' }, e.message));
  }
}

/** 下一章/本章语音还没好:轮询目录,好了就就地更新按钮和提示,不重绘正文(不打断阅读位置)。 */
function watchPending(bookId, idx, nextBtn, audioHint, needNext, needAudio) {
  poll(async () => {
    const chapters = await api.chapters(bookId);
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

/** 目录:当前章高亮、已读(≤ 最远进度)变淡;展开时自动把当前章滚到视野里。 */
function toc(bookId, chapters, current, readPos) {
  const label = { current: ' ← 正在读', read: '', unread: '' };
  const items = chapters.map((c) => {
    const mark = chapterMark(c.idx, current, readPos);
    return h('a', { href: `#/read/${bookId}/${c.idx}`, class: mark, 'aria-current': mark === 'current' ? 'page' : false },
      `第${c.idx}章 ${c.title}`, c.has_audio ? ' 🎧' : '', label[mark]);
  });
  const box = h('details', { class: 'toc' }, h('summary', {}, `目录(共 ${chapters.length} 章,已读 ${readPos} 章)`), items);
  box.addEventListener('toggle', () => box.open && box.querySelector('.current')?.scrollIntoView({ block: 'center' }));
  return box;
}

async function listen(bookId, idx, bookTitle, note) {
  try {
    const ok = await play(bookId, idx, bookTitle);
    note.textContent = ok ? '' : '这一章的语音还没准备好,先读文字吧。';
  } catch (e) {
    note.textContent = e.message;
  }
}

function waiting(box, book, bookId) {
  const hint = h('p', { class: 'muted' }, '第一章还在写,通常一两分钟,写好会自动打开。');
  fill(box, h('h2', {}, book.title), errorBanner(book), hint,
    h('button', { onclick: () => readerView(bookId) }, '立即刷新'));
  poll(async () => {
    if (!(await api.chapters(bookId)).length) return false;
    readerView(bookId);
    return true;
  }, { onGiveUp: () => { hint.textContent = '等得有点久了,后台可能遇到了问题。可以稍后点"立即刷新"再看。'; } });
}
