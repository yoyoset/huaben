// 目录:单独一页、按页取(每页 100 章)。原来是阅读页里的下拉框,一次渲染全部章节——
// 2026-10-02 用户:几千上万章时会把页面卡死。打开时直接翻到"正在读"的那一页,当前章高亮、已读变淡。
import { api } from '../api.js';
import { fill, h, mount, setTopTitle } from '../dom.js';
import { chapterMark, tocPage, tocPageOf } from '../logic.js';

const SIZE = 100;
const label = { current: ' ← 正在读', read: '', unread: '' };

export async function tocView(bookId, pageParam) {
  const box = h('div', {}, h('p', { class: 'muted' }, '加载中…'));
  mount(box);
  try {
    const book = await api.book(bookId);
    setTopTitle(book.title);
    const current = Math.max(1, book.last_opened);
    const pg = tocPage(pageParam ?? tocPageOf(current, SIZE), SIZE, book.ready_chapters);
    const chapters = book.ready_chapters ? await api.chapters(bookId, pg.from, pg.to) : [];
    const readPos = Math.max(book.read_pos, book.last_opened);
    const items = chapters.map((c) => {
      const mark = chapterMark(c.idx, current, readPos);
      return h('a', { href: `#/read/${bookId}/${c.idx}`, class: mark, 'aria-current': mark === 'current' ? 'page' : false },
        `第${c.idx}章 ${c.title}`, c.has_audio ? ' 🎧' : '', label[mark]);
    });
    fill(box,
      h('div', { class: 'row', style: 'justify-content:space-between' },
        h('a', { class: 'btn', href: `#/read/${bookId}` }, '← 回到阅读'),
        h('span', { class: 'muted' }, `共 ${book.ready_chapters} 章 · 读到第 ${readPos} 章`)),
      jumpForm(bookId, book.ready_chapters),
      pager(bookId, pg, book.ready_chapters),
      items.length ? h('div', { class: 'toc-list' }, items) : h('p', { class: 'muted' }, '还没有写好的章节。'),
      pager(bookId, pg, book.ready_chapters));
    box.querySelector('.current')?.scrollIntoView({ block: 'center' });
  } catch (e) {
    fill(box, h('div', { class: 'banner', role: 'alert' }, e.message));
  }
}

/** 上一页 / 选页(第 1~100 章…)/ 下一页。只有一页时不显示。 */
function pager(bookId, pg, total) {
  if (pg.pages <= 1) return null;
  const goPage = (p) => { location.hash = `#/toc/${bookId}/${p}`; };
  const select = h('select', { 'aria-label': '选择页', onchange: () => goPage(+select.value) },
    Array.from({ length: pg.pages }, (_, i) => {
      const r = tocPage(i + 1, SIZE, total);
      return h('option', { value: i + 1 }, `第 ${r.from}~${r.to} 章`);
    }));
  select.value = String(pg.page);
  return h('div', { class: 'row pager' },
    h('button', { disabled: pg.page <= 1, onclick: () => goPage(pg.page - 1) }, '← 上一页'),
    select,
    h('button', { disabled: pg.page >= pg.pages, onclick: () => goPage(pg.page + 1) }, '下一页 →'));
}

function jumpForm(bookId, total) {
  if (total < 2) return null;
  const input = h('input', { type: 'number', min: 1, max: total, placeholder: `1~${total}`, 'aria-label': '跳到第几章', style: 'width:7em' });
  const jump = () => {
    const n = Math.round(+input.value);
    if (n >= 1 && n <= total) location.hash = `#/read/${bookId}/${n}`;
  };
  input.addEventListener('keydown', (e) => { if (e.key === 'Enter') jump(); });
  return h('div', { class: 'row', style: 'margin:8px 0' }, h('span', {}, '跳到第'), input, h('span', {}, '章'),
    h('button', { onclick: jump }, '去'));
}
