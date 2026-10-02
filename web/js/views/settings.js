// 设置:模型接口(OpenRouter / OpenCode Zen / 自定义)、模型名、密钥。
// 密钥只进不出:输入框永远是空的,旁边只显示"已设置 …末4位";留空保存 = 不改密钥。
import { api } from '../api.js';
import { fill, h, mount, setTopTitle } from '../dom.js';

export async function settingsView() {
  setTopTitle('设置');
  const box = h('div', {}, h('p', { class: 'muted' }, '加载中…'));
  mount(box);
  try {
    render(box, await api.settings());
  } catch (e) {
    fill(box, h('div', { class: 'banner', role: 'alert' }, e.message));
  }
}

function field(label, input, hint) {
  return h('label', { class: 'field' }, h('span', {}, label), input, hint ? h('small', { class: 'muted' }, hint) : null);
}

function render(box, s) {
  const preset = h('select', { 'aria-label': '模型服务' },
    Object.entries(s.presets).map(([k, p]) => h('option', { value: k }, p.label)),
    h('option', { value: 'custom' }, '自定义(OpenAI 兼容接口)'));
  preset.value = s.preset;
  const baseUrl = h('input', { type: 'text', value: s.base_url, 'aria-label': '接口地址' });
  const model = h('input', { type: 'text', value: s.model, 'aria-label': '模型名' });
  const key = h('input', { type: 'password', autocomplete: 'off', 'aria-label': '密钥',
    placeholder: s.key_set ? `已设置 ${s.key_tail}(留空 = 不改)` : '粘贴密钥' });
  const msg = h('div', { class: 'note', hidden: true, role: 'status' });
  const say = (text) => { msg.textContent = text; msg.hidden = !text; };
  // 选预设 = 填好它的地址和推荐模型;之后仍可手改
  preset.onchange = () => {
    const p = s.presets[preset.value];
    if (p) { baseUrl.value = p.base_url; model.value = p.model; }
  };
  const save = async () => {
    say('保存中…');
    try {
      const next = await api.saveSettings({ base_url: baseUrl.value, model: model.value, api_key: key.value });
      render(box, next);
      box.querySelector('.note').hidden = false;
      box.querySelector('.note').textContent = '已保存,立即生效。可以点"测试连接"确认一下。';
    } catch (e) { say(e.message); }
  };
  const test = async () => {
    say('正在连接模型服务…');
    try {
      const r = await api.testSettings();
      say(r.ok ? `✅ 连接成功(${r.model},${(r.ms / 1000).toFixed(1)} 秒)。${r.cost_reported ? '' : '注意:这家服务不回报费用,书架上的花费金额会偏低。'}`
        : `❌ ${r.error}`);
    } catch (e) { say(e.message); }
  };
  fill(box,
    h('h2', {}, '模型'),
    field('服务', preset),
    field('接口地址', baseUrl, '以 /v1 结尾的 OpenAI 兼容地址'),
    field('模型名', model, 'OpenRouter 写 deepseek/deepseek-v4.1-flash;OpenCode Zen 写 deepseek-v4.1-flash'),
    field('密钥', key, s.key_from === 'env' ? '当前用的是服务器 .env 里的密钥;在这里填写会覆盖它' : ''),
    h('div', { class: 'row' }, h('button', { class: 'primary', onclick: save }, '保存'), h('button', { onclick: test }, '测试连接')),
    msg);
}
