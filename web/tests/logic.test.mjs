import assert from 'node:assert/strict';
import test from 'node:test';
import { afterEnded, nextChapter, nextRate, nextSleepOption, paragraphs, prevChapter, SLEEP_OPTIONS } from '../js/logic.js';

const chs = [{ idx: 3, has_audio: true }, { idx: 1, has_audio: true }, { idx: 2, has_audio: false }];

test('nextChapter / prevChapter 不依赖输入顺序,边界返回 null', () => {
  assert.equal(nextChapter(chs, 1).idx, 2);
  assert.equal(nextChapter(chs, 3), null);
  assert.equal(prevChapter(chs, 3).idx, 2);
  assert.equal(prevChapter(chs, 1), null);
  assert.equal(nextChapter([], 1), null);
});

test('afterEnded: 睡眠"本章结束"优先于一切', () => {
  assert.equal(afterEnded({ stopAtChapterEnd: true, next: { has_audio: true } }), 'stop');
});

test('afterEnded: 有下一章且有音频 → next;没音频或没章 → wait', () => {
  assert.equal(afterEnded({ stopAtChapterEnd: false, next: { has_audio: true } }), 'next');
  assert.equal(afterEnded({ stopAtChapterEnd: false, next: { has_audio: false } }), 'wait');
  assert.equal(afterEnded({ stopAtChapterEnd: false, next: null }), 'wait');
});

test('睡眠档位循环一圈回到"关闭"', () => {
  let i = 0;
  for (let k = 0; k < SLEEP_OPTIONS.length; k++) i = nextSleepOption(i);
  assert.equal(i, 0);
  assert.equal(SLEEP_OPTIONS[0].minutes, 0);
  assert.ok(SLEEP_OPTIONS.some((o) => o.endOfChapter));
});

test('语速循环,未知值回到第一档之后', () => {
  assert.equal(nextRate(1.0), 1.25);
  assert.equal(nextRate(0.85), 1.0);
  assert.equal(nextRate(9), 1.0); // indexOf=-1 → 下标 0
});

test('paragraphs 去空行并保留顺序', () => {
  assert.deepEqual(paragraphs('甲。\n\n 乙。 \n丙。'), ['甲。', '乙。', '丙。']);
  assert.deepEqual(paragraphs(null), []);
});

test('pollDelay 先密后疏、封顶 60 秒、超过次数放弃', async () => {
  const { pollDelay } = await import('../js/logic.js');
  assert.deepEqual([0, 1, 2, 3].map((a) => pollDelay(a)), [5, 10, 15, 20]);
  assert.equal(pollDelay(20), 60);
  assert.equal(pollDelay(39), 60);
  assert.equal(pollDelay(40), null);
  assert.equal(pollDelay(3, 3), null);
});

test('字号 ±1 且夹在范围内;行距档位循环;目录状态', async () => {
  const { stepFont, FONT_MIN, FONT_MAX, nextLeading, LEADINGS, chapterMark } = await import('../js/logic.js');
  assert.equal(stepFont(18, +1), 19);
  assert.equal(stepFont(FONT_MIN, -1), FONT_MIN);
  assert.equal(stepFont(FONT_MAX, +1), FONT_MAX);
  assert.equal(stepFont(undefined, +1), 19); // 存储里是坏值时回到默认 18 再调
  assert.equal(nextLeading(LEADINGS[LEADINGS.length - 1]), LEADINGS[0]);
  assert.equal(nextLeading(9), LEADINGS[0]);
  assert.deepEqual([1, 2, 3, 4].map((i) => chapterMark(i, 2, 3)), ['read', 'current', 'read', 'unread']);
});

test('统计页格式化:金额/时长/百分比', async () => {
  const { fmtUSD, fmtSeconds, fmtPct } = await import('../js/logic.js');
  assert.equal(fmtUSD(0.017), '$0.0170');
  assert.equal(fmtUSD(1.5), '$1.50');
  assert.equal(fmtUSD(0), '$0.00');
  assert.equal(fmtSeconds(15.4), '15 秒');
  assert.equal(fmtSeconds(80), '1 分 20 秒');
  assert.equal(fmtPct(0.5), '50%');
  assert.equal(fmtPct(undefined), '0%');
});

test('bookHome:开书阶段去对话,连载中去阅读', async () => {
  const { bookHome } = await import('../js/logic.js');
  assert.equal(bookHome({ id: 3, status: 'drafting' }), '#/opening/3');
  assert.equal(bookHome({ id: 3, status: 'serializing' }), '#/read/3');
});
