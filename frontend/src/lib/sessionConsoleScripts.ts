/** One-liner console scripts for copying session tokens from the browser. */
import { ALL_SESSIONS_PUSH_BOOKMARKLET } from "./bridge";

export const SESSION_CONSOLE_SCRIPTS: Record<string, { title: string; code: string }> = {
  hbomax: {
    title: "HBO Max / Max",
    code: `fetch('http://127.0.0.1:8000/api/bridge/session',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({batch:{hbomax:localStorage.getItem('token')},source:'console'})}).then(r=>r.json()).then(j=>console.log(j.success?'✓ Poslato u app':j));`,
  },
  voyo: {
    title: "Voyo",
    code: `fetch('http://127.0.0.1:8000/api/bridge/session',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({batch:{voyo:localStorage.getItem('token')||localStorage.getItem('apollo-cache-persist')},source:'console'})}).then(r=>r.json()).then(j=>console.log(j.success?'✓ Poslato u app':j));`,
  },
  hrti: {
    title: "HRTi",
    code: `fetch('http://127.0.0.1:8000/api/bridge/session',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({batch:{hrti:localStorage.getItem('token')},source:'console'})}).then(r=>r.json()).then(j=>console.log(j.success?'✓ Poslato u app':j));`,
  },
  rtsplaneta: {
    title: "RTS Planeta",
    code: `(function(){const k=Object.keys(localStorage).find(x=>/token|auth/i.test(x));const t=k?localStorage.getItem(k):'';fetch('http://127.0.0.1:8000/api/bridge/session',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({batch:{rtsplaneta:t},source:'console'})}).then(r=>r.json()).then(j=>console.log(j.success?'✓ Poslato u app':j));})();`,
  },
};

/** Push sessions directly to app (Tampermonkey-style, no paste). */
export const ALL_SESSIONS_BOOKMARKLET = ALL_SESSIONS_PUSH_BOOKMARKLET;

/** Clipboard fallback. */
export const ALL_SESSIONS_CLIPBOARD_BOOKMARKLET = `javascript:(function(){const d={voyo:localStorage.getItem('token')||localStorage.getItem('apollo-cache-persist'),hrti:localStorage.getItem('token'),rtsplaneta:(function(){const k=Object.keys(localStorage).find(x=>/token|auth/i.test(x));return k?localStorage.getItem(k):'';})(),hbomax:localStorage.getItem('token')};navigator.clipboard.writeText(JSON.stringify(d,null,2));alert('⚡ JSON kopiran — nalepite u Uvoz sesije.');})();`;
