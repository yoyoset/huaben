// 极小的 DOM 构造器。文本一律走 textContent,LLM 生成的内容永远不会被当 HTML 解析。
export function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === 'class') el.className = v;
    else if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
    else if (v === true) el.setAttribute(k, '');
    else if (v !== false && v != null) el.setAttribute(k, v);
  }
  return append(el, children);
}

// 展开嵌套数组、跳过 null/false(否则原生 append/replaceChildren 会把它们变成文字 "null" 或 "[object ...]")
function append(el, children) {
  for (const c of children.flat(Infinity)) {
    if (c == null || c === false) continue;
    el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return el;
}

/** 清空并重新填充 el。所有视图都用它,不要直接调 replaceChildren。 */
export function fill(el, ...children) {
  el.replaceChildren();
  return append(el, children);
}

export function mount(el) {
  const app = document.getElementById('app');
  fill(app, el);
  window.scrollTo(0, 0);
  app.focus({ preventScroll: true }); // 换页后焦点回到正文区:读屏从新页面开头读,键盘不必从顶部重新 Tab
}

export function setTopTitle(text) {
  document.getElementById('topbar-title').textContent = text || '';
}
