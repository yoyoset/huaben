// 书架。有书在后台生成时自动轮询刷新列表(进度、错误提示随之更新),全部备好后停止。
import { api } from '../api.js';
import { fill, h, mount, setTopTitle } from '../dom.js';
import { poll } from '../poll.js';

const STATUS = { drafting: '开书中', serializing: '连载中' };

function card(b) {
  const href = b.status === 'drafting' ? `#/opening/${b.id}` : `#/read/${b.id}`;
  const progress = b.status === 'serializing'
    ? ` · 已写 ${b.ready_chapters} 章 · 读到第 ${b.read_pos} 章 · 备好 ${b.buffered_ahead} 章${b.generating ? ' · 正在写…' : ''}`
    : '';
  return h('a', { class: 'card', href },
    h('h3', {}, b.title, ' ', h('span', { class: `chip ${b.status === 'serializing' ? 'live' : ''}` }, STATUS[b.status] ?? b.status)),
    h('div', { class: 'muted' }, b.genre || '', progress),
    // gen_error 非空 = 后台生成遇到问题:必须让用户看见,不能让 TA 以为一切正常
    b.gen_error ? h('div', { class: 'banner' }, `后台生成遇到问题:${b.gen_error}`) : null);
}

function render(box, books) {
  fill(box,
    h('div', { class: 'row' }, h('h2', {}, '书架'), h('button', { class: 'primary', onclick: newBook }, '＋ 开一本新书')),
    books.length ? books.map(card) : h('p', { class: 'muted' }, '还没有书。点上面的按钮,聊几句就能开始连载。'));
}

export async function shelfView() {
  setTopTitle('');
  const box = h('div', {}, h('p', { class: 'muted' }, '加载中…'));
  mount(box);
  try {
    const books = await api.books();
    render(box, books);
    if (books.some((b) => b.generating)) {
      poll(async () => {
        const latest = await api.books();
        render(box, latest);
        return !latest.some((b) => b.generating);
      });
    }
  } catch (e) {
    fill(box, h('div', { class: 'banner' }, e.message));
  }
}

async function newBook() {
  try {
    const b = await api.createBook('未命名');
    location.hash = `#/opening/${b.id}`;
  } catch (e) {
    alert(e.message);
  }
}
