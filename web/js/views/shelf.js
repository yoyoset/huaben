// 书架。有书在后台生成时自动轮询刷新列表(进度、错误提示随之更新),全部备好后停止。
import { api } from '../api.js';
import { fill, h, mount, setTopTitle } from '../dom.js';
import { bookHome, spendNote } from '../logic.js';
import { poll } from '../poll.js';
import { clearProfile, currentProfile } from '../profile.js';
import { voiceNoteEl } from './voice_note.js';

const STATUS = { drafting: '开书中', serializing: '连载中' };

function card(b, voice) {
  const href = bookHome(b);
  const progress = b.status === 'serializing'
    ? ` · 已写 ${b.ready_chapters} 章${b.pending_drafts ? `(另有 ${b.pending_drafts} 章已备稿,读到附近或点「预备」就放出)` : ''} · 读到第 ${b.read_pos} 章 · 备好 ${b.buffered_ahead} 章${b.generating ? (b.gen_error ? ' · 暂停中' : ' · 正在写…') : ''}`
    : '';
  return h('a', { class: 'card', href },
    h('h3', {}, b.title, ' ', h('span', { class: `chip ${b.status === 'serializing' ? 'live' : ''}` }, STATUS[b.status] ?? b.status)),
    h('div', { class: 'muted' }, b.genre || '', progress),
    // gen_error 非空 = 后台生成遇到问题:必须让用户看见,不能让 TA 以为一切正常
    // 书架会定时刷新,这里不用 role=alert,否则每次刷新读屏都会重新播报
    b.gen_error ? h('div', { class: 'banner' }, `后台生成遇到问题:${b.gen_error}`) : null,
    b.audio_error ? h('div', { class: 'note' }, `🎧 ${b.audio_error}`) : null,
    voiceNoteEl(b, voice, false));
}

function render(box, books, spend, voice) {
  const note = spendNote(spend);
  fill(box,
    h('div', { class: 'row' }, h('h2', {}, `${currentProfile()?.name ?? ''}的书架`), h('button', { class: 'primary', onclick: newBook }, '＋ 开一本新书')),
    note ? h('div', { class: 'note' }, note) : null,
    books.length ? books.map((b) => card(b, voice)) : h('p', { class: 'muted' }, '还没有书。点上面的按钮,聊几句就能开始连载。'));
}

export async function shelfView() {
  setTopTitle('');
  const box = h('div', {}, h('p', { class: 'muted' }, '加载中…'));
  mount(box);
  try {
    // 花费提醒取不到不影响书架(只是提醒)
    const me = currentProfile();
    const [books, spend, voice] = await Promise.all([api.books(me.id), api.spend().catch(() => null),
      api.voiceStatus().catch(() => null)]);
    render(box, books, spend, voice);
    if (books.some((b) => b.generating)) {
      poll(async () => {
        const latest = await api.books(me.id);
        render(box, latest, spend, voice);
        return !latest.some((b) => b.generating);
      });
    }
  } catch (e) {
    // 本机记着的读者在服务器上已不存在(比如恢复了旧库):回去重新选
    if (e.status === 404) { clearProfile(); location.replace('#/who'); return; }
    fill(box, h('div', { class: 'banner', role: 'alert' }, e.message));
  }
}

async function newBook() {
  try {
    const b = await api.createBook('未命名', currentProfile().id);
    location.hash = `#/opening/${b.id}`;
  } catch (e) {
    alert(e.message);
  }
}
