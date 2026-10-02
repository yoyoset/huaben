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

/**
 * 等待态轮询的间隔(秒):先密后疏,封顶 60 秒;超过 maxAttempts 次返回 null(放弃,让用户手动刷新)。
 * 一章生成通常 1~2 分钟,前几次密一点让读者尽快看到;长时间没结果说明后台在退避,没必要一直打。
 */
export const POLL_STEPS = [5, 10, 15, 20, 30, 45, 60];

export function pollDelay(attempt, maxAttempts = 40) {
  if (attempt >= maxAttempts) return null;
  return POLL_STEPS[Math.min(attempt, POLL_STEPS.length - 1)];
}

/** 阅读字号(px):每次 ±1,夹在 [14, 28]。 */
export const FONT_MIN = 14;
export const FONT_MAX = 28;

export function stepFont(size, dir) {
  const n = Number.isFinite(size) ? size : 18;
  return Math.min(FONT_MAX, Math.max(FONT_MIN, Math.round(n) + Math.sign(dir)));
}

/** 行距档位循环(未知值回到第一档)。 */
export const LEADINGS = [1.95, 2.2, 1.6, 1.8];

export function nextLeading(current) {
  return LEADINGS[(LEADINGS.indexOf(current) + 1) % LEADINGS.length];
}

/** 目录里每章的状态:当前章 / 已读(≤ 最远进度)/ 未读。 */
export function chapterMark(idx, current, readPos) {
  if (idx === current) return 'current';
  return idx <= readPos ? 'read' : 'unread';
}

/** 金额:小额保留 4 位(单章成本通常是零点几美分),大额 2 位。 */
export function fmtUSD(x) {
  const n = Number(x) || 0;
  return `$${n.toFixed(n !== 0 && Math.abs(n) < 0.1 ? 4 : 2)}`;
}

export function fmtSeconds(s) {
  const n = Math.round(Number(s) || 0);
  return n < 60 ? `${n} 秒` : `${Math.floor(n / 60)} 分 ${n % 60} 秒`;
}

export const fmtPct = (r) => `${Math.round((Number(r) || 0) * 100)}%`;

export const STEP_LABELS = {
  outline: '章纲', write: '正文', ledger: '入账', check: '核对打回', tts: '配音', error: '生成失败',
  volume_plan: '卷规划', volume_seal: '封卷', opening: '开书对话', finalize: '开书定稿',
};

/**
 * 读者要看的第 idx 章现在是什么状态(深链、书签、别的设备上的链接都会指向任意章号):
 *  - 'ready'   已写好
 *  - 'writing' 正是后台下一章要写的(紧接最新一章且后台在补货)→ 等它写好自动打开
 *  - 'later'   还没写到,而且不会马上写:后台只比读者进度多备几章,读者没往下读就不会写到它 → 不空等
 *  - 'missing' 章号不合法(< 1 或非整数)
 * 章号是连续的(只有定稿章占号),所以"比最新一章小却不在列表里"不会出现,归入 missing 兜底。
 */
export function chapterAvailability(chapters, idx, generating) {
  if (!Number.isInteger(idx) || idx < 1) return 'missing';
  if (chapters.some((c) => c.idx === idx)) return 'ready';
  const latest = chapters.reduce((m, c) => Math.max(m, c.idx), 0);
  if (idx <= latest) return 'missing';
  return idx === latest + 1 && generating ? 'writing' : 'later';
}

/** 一本书该去哪个页面:开书阶段去开书对话,连载中去阅读。书架、阅读页、开书页共用,避免各自判断不一致。 */
export function bookHome(book) {
  return book.status === 'drafting' ? `#/opening/${book.id}` : `#/read/${book.id}`;
}
