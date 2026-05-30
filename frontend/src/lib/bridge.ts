/** Tampermonkey bridge + bookmarklet helpers */
import { resolveApiUrl } from "./api";

export function getBridgeBase(): string {
  return resolveApiUrl("");
}

export function getUserscriptInstallUrl(): string {
  return resolveApiUrl("/api/bridge/userscript.js");
}

/** @deprecated use getUserscriptInstallUrl() — kept for older imports */
export const USERSCRIPT_INSTALL_URL = getUserscriptInstallUrl();

/** Bookmarklet: push all sessions directly to localhost (no paste). */
export function buildAllSessionsPushBookmarklet(): string {
  const bridgeUrl = resolveApiUrl("/api/bridge/session");
  return `javascript:(function(){const d={voyo:localStorage.getItem('token')||localStorage.getItem('apollo-cache-persist'),hrti:localStorage.getItem('token'),rtsplaneta:(function(){const k=Object.keys(localStorage).find(x=>/token|auth/i.test(x));return k?localStorage.getItem(k):'';})(),hbomax:localStorage.getItem('token')};fetch('${bridgeUrl}',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({batch:d,source:'bookmarklet'})}).then(r=>r.json()).then(j=>alert(j.success?'⚡ Sesija poslata u aplikaciju!':'Greška: '+(j.detail||j.message))).catch(()=>alert('Aplikacija nije pokrenuta (python run.py)?'));})();`;
}

export const ALL_SESSIONS_PUSH_BOOKMARKLET = buildAllSessionsPushBookmarklet();

export function buildHboSnifferBookmarklet(): string {
  const snifferUrl = resolveApiUrl("/api/sniffer/import");
  return `javascript:(function(){const m=window.location.href;const req={service:'hbomax',type:'manifest',url:m,title:document.title};fetch('${snifferUrl}',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(req)}).then(r=>r.ok?alert('⚡ Link uspešno snifovan i poslat u downloader!'):alert('Greška pri komunikaciji sa serverom.'));})();`;
}

export async function fetchUserscriptText(): Promise<string> {
  const res = await fetch(getUserscriptInstallUrl());
  if (!res.ok) throw new Error("Userscript nije dostupan");
  return res.text();
}
