// "谁在看":选一个读者进入他的书架,或添加一个新读者。不要密码(家用)。
import { api } from '../api.js';
import { fill, h, mount, setTopTitle } from '../dom.js';
import { setProfile } from '../profile.js';
import { applyPrefs } from '../reading_prefs.js';

export async function whoView() {
  setTopTitle('谁在看');
  const box = h('div', {}, h('p', { class: 'muted' }, '加载中…'));
  mount(box);
  try {
    render(box, await api.profiles());
  } catch (e) {
    fill(box, h('div', { class: 'banner', role: 'alert' }, e.message));
  }
}

function enter(p) {
  setProfile(p);
  applyPrefs(); // 换人后用他自己的字号/行距
  location.hash = '#/';
}

function render(box, profiles) {
  const input = h('input', { type: 'text', maxlength: 20, placeholder: '名字,比如:我、老婆', 'aria-label': '新读者的名字' });
  const err = h('div', { class: 'banner', role: 'alert', hidden: true });
  const add = async () => {
    const name = input.value.trim();
    if (!name) return input.focus();
    try {
      enter(await api.createProfile(name));
    } catch (e) {
      err.textContent = e.message;
      err.hidden = false;
    }
  };
  input.addEventListener('keydown', (e) => { if (e.key === 'Enter') add(); });
  fill(box,
    h('h2', {}, profiles.length ? '谁在看?' : '先给自己起个名字'),
    h('div', { class: 'profiles' }, profiles.map((p) =>
      h('button', { class: 'profile-card', onclick: () => enter(p) },
        h('strong', {}, p.name), h('span', { class: 'muted' }, `${p.books} 本书`)))),
    h('div', { class: 'row', style: 'margin-top:12px' }, input,
      h('button', { class: profiles.length ? '' : 'primary', onclick: add }, '＋ 添加读者')),
    err);
}
