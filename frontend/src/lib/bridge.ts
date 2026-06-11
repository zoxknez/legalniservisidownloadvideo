/** Tampermonkey bridge + bookmarklet helpers */
import { resolveApiUrl } from "./api";

export function getBridgeBase(): string {
  return resolveApiUrl("");
}

export function getUserscriptInstallUrl(): string {
  return resolveApiUrl("/api/bridge/userscript.js");
}

/** @deprecated use getUserscriptInstallUrl() - kept for older imports */
export const USERSCRIPT_INSTALL_URL = getUserscriptInstallUrl();

/** Collect EON cookies when bookmarklet runs on *.eon.tv (HttpOnly cookies are not included). */
function buildEonCookieCollectorJs(): string {
  return `(function(){try{if(!/eon\\.tv/i.test(location.hostname))return'';const c={};(document.cookie||'').split(';').forEach(p=>{const i=p.indexOf('=');if(i>0){const k=p.slice(0,i).trim();try{c[k]=decodeURIComponent(p.slice(i+1).trim().replace(/\\+/g,' '));}catch(e){c[k]=p.slice(i+1).trim();}}});return Object.keys(c).length?JSON.stringify({cookies:c}):'';}catch(e){return'';}})()`;
}

/** Collect HRTi token plus CustomerId when the browser exposes it. */
export function buildHrtiSessionCollectorJs(): string {
  return `(function(){const t=localStorage.getItem('token')||'';if(!t)return'';function jwt(x){try{const p=String(x).replace(/^(Bearer|Client)\\s+/i,'').split('.')[1];if(!p)return{};return JSON.parse(atob(p.replace(/-/g,'+').replace(/_/g,'/')));}catch(e){return{};}}function walk(o,d,rx){if(!o||d>6)return'';if(typeof o!=='object')return'';if(Array.isArray(o)){for(const it of o){const r=walk(it,d+1,rx);if(r)return r;}return'';}for(const k in o){const v=o[k];if(rx.test(k)&&v!=null&&typeof v!=='object')return String(v).trim();}for(const k in o){const r=walk(o[k],d+1,rx);if(r)return r;}return'';}function scan(rx){for(let i=0;i<localStorage.length;i++){const k=localStorage.key(i)||'';const v=localStorage.getItem(k)||'';if(rx.test(k)&&v)return v.trim();try{const r=walk(JSON.parse(v),0,rx);if(r)return r;}catch(e){}}return'';}const cidRx=/^(customerid|customer_id|userid|user_id|customerreferenceid|customer_reference_id)$/i;const emailRx=/^(email|username|useremail|mail)$/i;const payload=jwt(t);const cid=walk(payload,0,/^(customerid|customer_id|userid|user_id|customerreferenceid|customer_reference_id|sub)$/i)||scan(cidRx);const email=walk(payload,0,emailRx)||scan(emailRx);const out={token:t};if(cid)out.customer_id=cid;if(email)out.email=email;return JSON.stringify(out);})()`;
}

/** Bookmarklet: push all sessions directly to localhost (no paste). */
export function buildAllSessionsPushBookmarklet(): string {
  const bridgeUrl = resolveApiUrl("/api/bridge/session");
  const eonCollector = buildEonCookieCollectorJs();
  const hrtiCollector = buildHrtiSessionCollectorJs();
  const voyoCollector =
    "(function(){const t=localStorage.getItem('token')||localStorage.getItem('apollo-cache-persist');if(!t)return'';let v='rs';const h=location.hostname;if(h.includes('voyo.hr')||h.includes('rtl.hr'))v='hr';return JSON.stringify({token:t,variant:v});})()";
  return `javascript:(function(){const d={voyo:${voyoCollector},hrti:${hrtiCollector},rtsplaneta:(function(){const k=Object.keys(localStorage).find(x=>/token|auth/i.test(x));return k?localStorage.getItem(k):'';})(),hbomax:localStorage.getItem('token'),eon:${eonCollector}};Object.keys(d).forEach(k=>{if(!d[k])delete d[k];});if(!Object.keys(d).length){alert('Nema sesije na ovoj stranici. Otvorite sajt servisa (Voyo, HRTi, RTS, Max, EON) pa ponovo kliknite bookmarklet.');return;}fetch('${bridgeUrl}',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({batch:d,source:'bookmarklet'})}).then(r=>r.json()).then(j=>alert(j.success?'⚡ Sesija poslata u aplikaciju!':'Greška: '+(j.detail||j.message))).catch(()=>alert('Aplikacija nije pokrenuta (python run.py)?'));})();`;
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
