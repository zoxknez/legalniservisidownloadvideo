/** One-liner console scripts for copying session tokens from the browser. */
import { resolveApiUrl } from "./api";
import {
  buildAllSessionsPushBookmarklet,
  buildHboSnifferBookmarklet,
} from "./bridge";

export function buildSessionConsoleScripts(): Record<string, { title: string; code: string }> {
  const bridgeUrl = resolveApiUrl("/api/bridge/session");
  return {
    hbomax: {
      title: "HBO Max / Max",
      code: `fetch('${bridgeUrl}',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({batch:{hbomax:localStorage.getItem('token')},source:'console'})}).then(r=>r.json()).then(j=>console.log(j.success?'✓ Poslato u app':j));`,
    },
    voyo: {
      title: "Voyo",
      code: `fetch('${bridgeUrl}',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({batch:{voyo:localStorage.getItem('token')||localStorage.getItem('apollo-cache-persist')},source:'console'})}).then(r=>r.json()).then(j=>console.log(j.success?'✓ Poslato u app':j));`,
    },
    hrti: {
      title: "HRTi",
      code: `fetch('${bridgeUrl}',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({batch:{hrti:localStorage.getItem('token')},source:'console'})}).then(r=>r.json()).then(j=>console.log(j.success?'✓ Poslato u app':j));`,
    },
    rtsplaneta: {
      title: "RTS Planeta",
      code: `(function(){const k=Object.keys(localStorage).find(x=>/token|auth/i.test(x));const t=k?localStorage.getItem(k):'';fetch('${bridgeUrl}',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({batch:{rtsplaneta:t},source:'console'})}).then(r=>r.json()).then(j=>console.log(j.success?'✓ Poslato u app':j));})();`,
    },
  };
}

/** Push sessions directly to app (Tampermonkey-style, no paste). */
export const ALL_SESSIONS_BOOKMARKLET = buildAllSessionsPushBookmarklet();

/** HBO Max manifest sniffer bookmarklet. */
export const HBO_SNIFFER_BOOKMARKLET = buildHboSnifferBookmarklet();

/** Clipboard fallback. */
export const ALL_SESSIONS_CLIPBOARD_BOOKMARKLET = `javascript:(function(){const d={voyo:localStorage.getItem('token')||localStorage.getItem('apollo-cache-persist'),hrti:localStorage.getItem('token'),rtsplaneta:(function(){const k=Object.keys(localStorage).find(x=>/token|auth/i.test(x));return k?localStorage.getItem(k):'';})(),hbomax:localStorage.getItem('token')};navigator.clipboard.writeText(JSON.stringify(d,null,2));alert('⚡ JSON kopiran — nalepite u Uvoz sesije.');})();`;
