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
    const [book, s] = await Promise.all([api.book(bookId), api.stats(bookId)]);
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
        tile('累计花费', fmtUSD(s.total_cost_usd), `开书 ${fmtUSD(s.cost_breakdown_usd.opening)}`)),
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
    fill(box, h('div', { class: 'banner' }, e.message));
  }
}
