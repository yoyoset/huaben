// 书的运行统计:回答"贵不贵、慢不慢、稳不稳"。口径见 huaben/stats.py。
// 技术细节(失败原因原文)放在折叠区里,默认只看人话数字。
import { api } from '../api.js';
import { fill, h, mount, setTopTitle } from '../dom.js';
import { fmtPct, fmtSeconds, fmtUSD, STEP_LABELS } from '../logic.js';

const tile = (label, value, hint) =>
  h('div', { class: 'stat' }, h('div', { class: 'stat-value' }, value), h('div', { class: 'muted' }, label),
    hint ? h('div', { class: 'stat-hint' }, hint) : null);

export async function statsView(bookId) {
  const box = h('div', {}, h('p', { class: 'muted' }, '加载中…'));
  mount(box);
  try {
    const [book, s, fr] = await Promise.all([api.book(bookId), api.stats(bookId), api.foreshadows(bookId)]);
    setTopTitle(`${book.title} · 统计`);
    const failures = Object.entries(s.failures);
    fill(box,
      h('div', { class: 'row' }, h('a', { class: 'btn', href: `#/read/${bookId}` }, '← 回到阅读')),
      h('h2', {}, '运行统计'),
      h('div', { class: 'stats' },
        tile('已写章数', String(s.chapters)),
        tile('单章平均成本', fmtUSD(s.avg_cost_usd), '含被打回的稿子与分卷规划'),
        tile('单章平均耗时', fmtSeconds(s.avg_seconds)),
        tile('重写率', fmtPct(s.rewrite_rate), `平均 ${s.avg_attempts.toFixed(1)} 稿`),
        tile('已配音', `${s.voiced}/${s.chapters}`),
        tile('累计花费', fmtUSD(s.total_cost_usd), `开书 ${fmtUSD(s.cost_breakdown_usd.opening)}`),
        canonTile(s.canon)),
      foreshadowSection(fr),
      h('h2', {}, '问题记录'),
      failures.length
        ? h('ul', {}, failures.map(([step, n]) => h('li', {}, `${STEP_LABELS[step] ?? step}:${n} 次`)))
        : h('p', { class: 'muted' }, '没有失败记录。'),
      s.recent_failures.length
        ? h('details', {}, h('summary', {}, '最近的失败详情(技术信息)'),
          s.recent_failures.map((f) => h('p', { class: 'muted mono' },
            `${f.created_at} · ${STEP_LABELS[f.step] ?? f.step}${f.chapter_idx ? ` · 第${f.chapter_idx}章` : ''} · ${f.note}`)))
        : null);
  } catch (e) {
    fill(box, h('div', { class: 'banner', role: 'alert' }, e.message));
  }
}

/** 世界设定定本:每章都整段带上,封卷时由模型合并;过长说明可能没去重,会推高每章成本。 */
function canonTile(c) {
  if (!c.chars) return tile('世界设定定本', '—', '第一卷封卷后生成');
  const hint = c.too_long ? `偏长(超过 ${c.warn_chars} 字):每章都要带上,可能合并时没去重` : `${c.lines} 条,每章都会带上`;
  return h('div', { class: c.too_long ? 'stat warn' : 'stat' },
    h('div', { class: 'stat-value' }, `${c.chars} 字`), h('div', { class: 'muted' }, '世界设定定本'),
    h('div', { class: 'stat-hint' }, hint));
}

/** 伏笔回收:全书汇总 + 每卷"计划收 / 实际收 / 没收"(验收项:卷内伏笔有回收记录)。 */
function foreshadowSection(fr) {
  const t = fr.total;
  const ids = (xs) => (xs.length ? xs.map((i) => `#${i}`).join('、') : '无');
  return h('section', {},
    h('h2', {}, '伏笔'),
    h('div', { class: 'stats' },
      tile('已埋', String(t.planted)), tile('已回收', String(t.resolved)), tile('未回收', String(t.open)),
      tile('平均几章后回收', t.avg_chapters_to_resolve == null ? '—' : t.avg_chapters_to_resolve.toFixed(1))),
    t.oldest_open.length
      ? h('p', { class: 'muted' }, '拖得最久的:', t.oldest_open.map((o) => `#${o.id} ${o.content}(已 ${o.age} 章)`).join(';'))
      : null,
    h('ul', {}, fr.volumes.map((v) => h('li', {},
      `第${v.idx}卷${v.status === 'sealed' ? '(已封卷)' : '(进行中)'}:埋 ${v.planted} 条;计划收 ${ids(v.planned_resolve)};`
      + `已收 ${ids(v.resolved)}${v.missed.length ? `;${v.status === 'sealed' ? '没收' : '尚未收'} ${ids(v.missed)}` : ''}`))));
}
