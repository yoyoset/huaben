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
