// 阅读:最近读到的章(或指定章)、目录、上/下章、"听这一章"。
import { api } from '../api.js';
import { fill, h, mount, setTopTitle } from '../dom.js';
import { nextChapter, paragraphs, prevChapter } from '../logic.js';
import { play } from '../player.js';

const go = (bookId, idx) => { location.hash = `#/read/${bookId}/${idx}`; };

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
    fill(box, 
      book.gen_error ? h('div', { class: 'banner' }, `后台生成遇到问题:${book.gen_error}`) : null,
      h('h1', { class: 'chapter-title' }, `第${idx}章 ${ch.title}`),
      h('div', { class: 'row' },
        h('button', { class: 'primary', onclick: () => listen(bookId, idx, book.title, note) }, '🎧 听这一章'),
        h('span', { class: 'muted' }, ch.audio_url ? '' : '语音还在准备')),
      h('div', { class: 'chapter-body' }, paragraphs(ch.body).map((p) => h('p', {}, p))),
      h('div', { class: 'chapter-nav' },
        h('button', { disabled: !prev, onclick: () => go(bookId, prev.idx) }, '← 上一章'),
        h('button', { class: 'primary', disabled: !next, onclick: () => go(bookId, next.idx) }, next ? '下一章 →' : '下一章还在写'),
      ),
      h('details', { class: 'toc' }, h('summary', {}, `目录(共 ${chapters.length} 章)`),
        chapters.map((c) => h('a', { href: `#/read/${bookId}/${c.idx}` }, `第${c.idx}章 ${c.title}`, c.has_audio ? ' 🎧' : ''))),
      note,
    );
  } catch (e) {
    fill(box, h('div', { class: 'banner' }, e.message));
  }
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
  fill(box, 
    h('h2', {}, book.title),
    book.gen_error ? h('div', { class: 'banner' }, `后台生成遇到问题:${book.gen_error}`) : null,
    h('p', { class: 'muted' }, '第一章还在写,通常一两分钟。写好后刷新即可。'),
    h('button', { onclick: () => readerView(bookId) }, '刷新'));
}
