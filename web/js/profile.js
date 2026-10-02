// 当前读者(profile = 人)。记在本机浏览器里:同一台手机通常是同一个人在用,下次打开不用再选。
// 换人点顶栏的名字。存储不可用(隐私模式等)时每次打开都会回到"谁在看",功能照常。
const KEY = 'huaben.profile';

export function currentProfile() {
  try { return JSON.parse(localStorage.getItem(KEY) || 'null'); } catch { return null; }
}

export function setProfile(p) {
  try { localStorage.setItem(KEY, JSON.stringify({ id: p.id, name: p.name })); } catch { /* 不记忆即可 */ }
  showProfile();
}

export function clearProfile() {
  try { localStorage.removeItem(KEY); } catch { /* 同上 */ }
  showProfile();
}

/** 顶栏右侧显示当前读者,点它换人。 */
export function showProfile() {
  const el = document.getElementById('topbar-who');
  if (!el) return;
  const p = currentProfile();
  el.textContent = p ? `👤 ${p.name}` : '';
  el.hidden = !p;
}
