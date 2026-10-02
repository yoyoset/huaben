// 开书对话:聊几句 → 点"开书"。样章直接粘贴进对话框(≥200 字会被原文保存作为文风样本)。
import { api } from '../api.js';
import { h, mount, setTopTitle } from '../dom.js';

const GREETING = '想看什么样的故事?可以说说题材、喜欢的作品,最好直接贴一段你最喜欢的文字——我会照着它的味道写。';

export async function openingView(bookId) {
  setTopTitle('开一本新书');
  const chat = h('div', { class: 'chat' });
  const input = h('textarea', { rows: 4, 'aria-label': '你的回复', placeholder: '说说你想看的故事…(可以直接粘贴样章)' });
  const send = h('button', { class: 'primary' }, '发送');
  const finish = h('button', {}, '开书');
  const err = h('div', { class: 'banner', role: 'alert', hidden: true });
  let userCount = 0;

  const bubble = (role, text) => {
    const el = h('div', { class: `bubble ${role}` }, text);
    chat.append(el);
    return el;
  };
  const showErr = (m) => { err.textContent = m; err.hidden = !m; };
  const busy = (on) => { send.disabled = finish.disabled = on; };

  try {
    const hist = await api.openingHistory(bookId);
    if (!hist.length) bubble('assistant', GREETING);
    hist.forEach((m) => { bubble(m.role, m.content); if (m.role === 'user') userCount++; });
  } catch (e) { showErr(e.message); }
  finish.disabled = userCount === 0;

  send.onclick = async () => {
    const text = input.value.trim();
    if (!text) return;
    busy(true); showErr('');
    const mine = bubble('user', text); input.value = '';
    try {
      const r = await api.say(bookId, text);
      bubble('assistant', r.reply);
      userCount++;
      if (r.ready) finish.classList.add('primary'); // 向导觉得问够了:高亮"开书",但不强制
    } catch (e) {
      // 服务端失败时这条消息没有保存:撤回气泡、把原文放回输入框,用户点发送即可重试,不会重复
      mine.remove(); input.value = text; showErr(e.message);
    }
    busy(false); finish.disabled = userCount === 0;
  };

  finish.onclick = async () => {
    busy(true); showErr('');
    finish.textContent = '正在开书(约 1 分钟)…';
    try {
      await api.finalize(bookId);
      location.hash = `#/read/${bookId}`;
    } catch (e) {
      showErr(e.message); // 后端文案已写明"可以重试"
      finish.textContent = '开书';
      busy(false);
    }
  };

  mount(h('div', {}, chat, err, input, h('div', { class: 'row', style: 'margin-top:8px' }, send, finish)));
}
