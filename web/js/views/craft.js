// 写法设定:叙事结构 / 文笔 / 伏笔布局 / 节奏 + 补充要求(2026-10-03 用户:开书时就该给模板选,
// 叙事方式、伏笔长短这些基础的东西读者自己想不到去提)。开书页里内嵌一份,开书后在 #/craft/书 随时改。
// 改了就存,从下一章起生效;选项说明由服务端给(huaben/craft.py),这里只负责摆出来。
import { api } from '../api.js';
import { fill, h, mount, setTopTitle } from '../dom.js';

/** 设定面板。改动即保存,status 行告诉读者存上了没有。 */
export async function craftPanel(bookId) {
  const box = h('div', { class: 'craft' }, h('p', { class: 'muted' }, '加载写法选项…'));
  try {
    const [options, craft] = await Promise.all([api.craftOptions(), api.craft(bookId)]);
    const status = h('p', { class: 'muted', role: 'status' });
    const save = async () => {
      status.textContent = '保存中…';
      try {
        Object.assign(craft, await api.saveCraft(bookId, craft));
        status.textContent = '已保存,从下一章起按新的写法写。';
      } catch (e) { status.textContent = e.message; }
    };
    const groups = options.map((cat) => h('fieldset', {},
      h('legend', {}, cat.label),
      cat.choices.map((ch) => h('label', { class: 'craft-choice' },
        h('input', { type: 'radio', name: `craft-${cat.key}`, value: ch.value, checked: craft[cat.key] === ch.value,
          onchange: () => { craft[cat.key] = ch.value; save(); } }),
        h('span', {}, h('strong', {}, ch.label), h('span', { class: 'stat-hint' }, ch.hint))))));
    const notes = h('textarea', { rows: 3, maxlength: 1000, placeholder: '其他要求(可不填):比如"每章至少三个笑点""主角说话要损"' }, craft.notes);
    notes.addEventListener('change', () => { craft.notes = notes.value.trim(); save(); });
    fill(box, groups, h('label', {}, h('div', {}, '补充要求'), notes), status);
  } catch (e) {
    fill(box, h('div', { class: 'banner', role: 'alert' }, e.message));
  }
  return box;
}

export async function craftView(bookId) {
  const box = h('div', {}, h('p', { class: 'muted' }, '加载中…'));
  mount(box);
  try {
    const book = await api.book(bookId);
    setTopTitle(book.title);
    fill(box,
      h('div', { class: 'row', style: 'justify-content:space-between' },
        h('a', { class: 'btn', href: `#/read/${bookId}` }, '← 回到阅读'), h('span', { class: 'muted' }, '写法设定')),
      h('p', { class: 'muted' }, '已经写好的章不会改;下一章起按这里的设定写。'),
      await craftPanel(bookId),
      expandBox(bookId));
  } catch (e) {
    fill(box, h('div', { class: 'banner', role: 'alert' }, e.message));
  }
}

/** 已开书的书:补充原创设定(只往世界观里加,不推翻已写的;补充写在原设定后面、带日期,想撤回删掉那一节即可)。 */
function expandBox(bookId) {
  const out = h('p', { class: 'muted', role: 'status' });
  const btn = h('button', {
    onclick: async () => {
      btn.disabled = true;
      out.textContent = '设定编辑正在构思(十几秒)…';
      try {
        const r = await api.expandWorld(bookId);
        out.textContent = `已补充进世界观,下一章起生效。${r.why}

${r.additions}`;
      } catch (e) { out.textContent = e.message; }
      btn.disabled = false;
    },
  }, '🪄 补充原创设定(不推翻已写的)');
  return h('section', { class: 'craft-box' },
    h('h2', {}, '世界观太套路?'),
    h('p', { class: 'muted' }, '按上面的「想象力」档位,给这本书补一套原创的核心机制、地方和势力;和已经写好的章节不矛盾。'),
    btn, h('div', { style: 'white-space:pre-wrap' }, out));
}
