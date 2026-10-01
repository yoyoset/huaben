// 纯函数:不碰 DOM、不碰网络,可用 `node --test` 直接测。

/** 在已定稿章列表里找 idx 的下一章;没有返回 null。 */
export function nextChapter(chapters, idx) {
  return chapters.filter((c) => c.idx > idx).sort((a, b) => a.idx - b.idx)[0] ?? null;
}

export function prevChapter(chapters, idx) {
  return chapters.filter((c) => c.idx < idx).sort((a, b) => b.idx - a.idx)[0] ?? null;
}

/**
 * 一章播完后该做什么。
 *  - 睡眠定时选了"本章结束" → 停
 *  - 有下一章且有音频 → 接着播
 *  - 否则 → 等(下一章还在后台生成,或还没配好音)
 */
export function afterEnded({ stopAtChapterEnd, next }) {
  if (stopAtChapterEnd) return 'stop';
  if (next && next.has_audio) return 'next';
  return 'wait';
}

export const SLEEP_OPTIONS = [
  { label: '关闭', minutes: 0, endOfChapter: false },
  { label: '15 分钟', minutes: 15, endOfChapter: false },
  { label: '30 分钟', minutes: 30, endOfChapter: false },
  { label: '60 分钟', minutes: 60, endOfChapter: false },
  { label: '本章结束', minutes: 0, endOfChapter: true },
];

/** 循环切换到下一个睡眠定时档位(按钮每点一下切一档)。 */
export function nextSleepOption(currentIndex) {
  return (currentIndex + 1) % SLEEP_OPTIONS.length;
}

export const RATES = [1.0, 1.25, 1.5, 0.85];

export function nextRate(current) {
  const i = RATES.indexOf(current);
  return RATES[(i + 1) % RATES.length];
}

/** 把正文按空行/换行切成段落,过滤空段。 */
export function paragraphs(text) {
  return String(text ?? '').split(/\n+/).map((s) => s.trim()).filter(Boolean);
}
