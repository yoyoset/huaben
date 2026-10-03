// 人物志(路线 61):账本里的人物现状只有模型看得到,读者想回顾"这人是谁、能力是什么、什么关系"时没有入口。
// 这一页把读过的人物整理出来:招牌能力与阶段、关系、知情;不动账本,纯展示。
import { api } from '../api.js';
import { fill, h, mount, setTopTitle } from '../dom.js';

const line = (label, value) => (value ? h('div', { class: 'cast-line' }, h('span', { class: 'cast-label' }, label), value) : null);

function characterCard(c) {
  const state = c.alive ? '' : h('span', { class: 'muted' }, ' · 已故');
  return h('article', { class: c.core ? 'cast-card core' : 'cast-card' },
    h('h3', {}, c.name, c.core ? h('span', { class: 'tag' }, '核心') : null, state),
    c.role ? h('div', { class: 'muted' }, c.role) : null,
    c.profile ? h('p', {}, c.profile) : null,
    c.signature_text ? h('div', { class: 'cast-signature' }, h('span', { class: 'cast-label' }, '招牌'), c.signature_text) : null,
    line('位置', c.location),
    line('能力', c.abilities),
    line('关系', c.relations),
    c.knows.length
      ? h('div', { class: 'cast-line' }, h('span', { class: 'cast-label' }, '知道'),
        c.knows.join('、') + (c.knows_more ? `(另有 ${c.knows_more} 条)` : ''))
      : null,
    c.updated_ch ? h('div', { class: 'stat-hint' }, `最近更新:第 ${c.updated_ch} 章`) : h('div', { class: 'stat-hint' }, '尚未登场'));
}

export async function castView(bookId) {
  const box = h('div', {}, h('p', { class: 'muted' }, '加载中…'));
  mount(box);
  try {
    const [book, data] = await Promise.all([api.book(bookId), api.cast(bookId)]);
    setTopTitle(`${book.title} · 人物志`);
    const chars = data.characters;
    fill(box,
      h('div', { class: 'row' }, h('a', { class: 'btn', href: `#/read/${bookId}` }, '← 回到阅读')),
      h('h2', {}, '人物志'),
      chars.length
        ? h('div', { class: 'cast' }, chars.map(characterCard))
        : h('p', { class: 'muted' }, '还没有人物记录:开书定稿后,读过的人物会出现在这里。'));
  } catch (e) {
    fill(box, h('div', { class: 'banner', role: 'alert' }, e.message));
  }
}
