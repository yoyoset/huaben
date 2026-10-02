// 配音提示条:电脑没开时提醒开机,并让读者决定要不要先用 edge-tts 配。文案判断在 logic.voiceNote(纯函数)。
import { api } from '../api.js';
import { h } from '../dom.js';
import { voiceNote } from '../logic.js';

/** withButton=false:书架卡片整张是链接,里面不放按钮,只显示文字。 */
export function voiceNoteEl(book, voice, withButton = true) {
  const n = voiceNote(book.audio_pending, voice);
  if (!n) return null;
  const text = h('span', {}, n.text);
  const box = h('div', { class: 'note' }, text);
  if (n.offerFallback && withButton) {
    const btn = h('button', {
      onclick: async () => {
        btn.disabled = true;
        try {
          await api.voiceFallback(book.id);
          text.textContent = '🎧 已开始用 edge-tts 配音,配好一章就能听一章(电脑开机后会换成高质量版)';
          btn.remove();
        } catch (e) {
          text.textContent = `🎧 ${e.message}`;
          btn.disabled = false;
        }
      },
    }, '先用 edge-tts 配');
    box.append(' ', btn);
  }
  return box;
}
