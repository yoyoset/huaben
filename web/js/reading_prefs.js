// 阅读偏好(字号/行距):存在本机浏览器里。localStorage 可能不可用(隐私模式等),
// 读写都包 try/catch,不可用时照常显示默认值,只是不记忆。
import { h } from './dom.js';
import { LEADINGS, nextLeading, stepFont } from './logic.js';
import { currentProfile } from './profile.js';

// 每人一份:同一台平板可能两个人轮流用,字号习惯各不相同
const key = () => `huaben.reading.${currentProfile()?.id ?? 0}`;
const DEFAULTS = { fontSize: 18, leading: LEADINGS[0], scrollSpeed: 1 };

export function load() {
  try {
    return { ...DEFAULTS, ...JSON.parse(localStorage.getItem(key()) || '{}') };
  } catch {
    return { ...DEFAULTS };
  }
}

export function save(p) {
  try { localStorage.setItem(key(), JSON.stringify(p)); } catch { /* 不可用:不记忆即可 */ }
}

export function applyPrefs(p = load()) {
  const root = document.documentElement.style;
  root.setProperty('--read-size', `${p.fontSize}px`);
  root.setProperty('--read-leading', String(p.leading));
}

/** 阅读页顶部的小工具条:A- / A+ / 行距。 */
export function prefsToolbar() {
  let p = load();
  const update = (next) => { p = next; save(p); applyPrefs(p); };
  return h('div', { class: 'row reading-tools', role: 'group', 'aria-label': '阅读设置' },
    h('button', { 'aria-label': '缩小字号', onclick: () => update({ ...p, fontSize: stepFont(p.fontSize, -1) }) }, 'A-'),
    h('button', { 'aria-label': '放大字号', onclick: () => update({ ...p, fontSize: stepFont(p.fontSize, +1) }) }, 'A+'),
    h('button', { 'aria-label': '切换行距', onclick: () => update({ ...p, leading: nextLeading(p.leading) }) }, '行距'));
}
