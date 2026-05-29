/** Tampermonkey bridge + bookmarklet helpers */

export const BRIDGE_BASE = "http://127.0.0.1:8000";

export const USERSCRIPT_INSTALL_URL = `${BRIDGE_BASE}/api/bridge/userscript.js`;

/** Bookmarklet: push all sessions directly to localhost (no paste). */
export const ALL_SESSIONS_PUSH_BOOKMARKLET = `javascript:(function(){const d={voyo:localStorage.getItem('token')||localStorage.getItem('apollo-cache-persist'),hrti:localStorage.getItem('token'),rtsplaneta:(function(){const k=Object.keys(localStorage).find(x=>/token|auth/i.test(x));return k?localStorage.getItem(k):'';})(),hbomax:localStorage.getItem('token')};fetch('${BRIDGE_BASE}/api/bridge/session',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({batch:d,source:'bookmarklet'})}).then(r=>r.json()).then(j=>alert(j.success?'⚡ Sesija poslata u aplikaciju!':'Greška: '+(j.detail||j.message))).catch(()=>alert('Aplikacija nije pokrenuta (python run.py)?'));})();`;

export async function fetchUserscriptText(): Promise<string> {
  const res = await fetch(USERSCRIPT_INSTALL_URL);
  if (!res.ok) throw new Error("Userscript nije dostupan");
  return res.text();
}
