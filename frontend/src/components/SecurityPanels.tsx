import { useCallback, useRef, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  KeyRound,
  Loader2,
  Shield,
  Upload,
  Wand2,
} from "lucide-react";
import { apiFetch } from "../lib/api";
import { SESSION_CONSOLE_SCRIPTS } from "../lib/sessionConsoleScripts";

export interface CredentialFieldStatus {
  configured: boolean;
  stored_in_keyring: boolean;
  in_config_json: boolean;
}

export interface ServiceCredentialSecurity {
  keyring_available: boolean;
  fields: Record<string, CredentialFieldStatus>;
}

export type CredentialsSecurityMap = Record<string, ServiceCredentialSecurity>;

const SERVICE_LABELS: Record<string, string> = {
  voyo: "Voyo",
  eon: "EON TV",
  hrti: "HRTi",
  rtsplaneta: "RTS Planeta",
  hbomax: "HBO Max",
};

const FIELD_LABELS: Record<string, string> = {
  password: "Lozinka",
  token: "Token",
  access_token: "Access token",
  secure_streaming_token: "Streaming token",
};

function fieldBadge(field: string, st: CredentialFieldStatus) {
  if (!st.configured) {
    return (
      <span className="text-[10px] text-text-muted border border-white/10 px-2 py-0.5 rounded">
        {FIELD_LABELS[field] || field}: nije podešeno
      </span>
    );
  }
  if (st.stored_in_keyring) {
    return (
      <span className="text-[10px] font-bold text-emerald-400 bg-emerald-500/10 border border-emerald-500/30 px-2 py-0.5 rounded flex items-center gap-1">
        <KeyRound className="w-3 h-3" />
        {FIELD_LABELS[field] || field}: Windows keyring
      </span>
    );
  }
  if (st.in_config_json) {
    return (
      <span className="text-[10px] font-bold text-amber-400 bg-amber-500/10 border border-amber-500/30 px-2 py-0.5 rounded">
        {FIELD_LABELS[field] || field}: u config.json (migrira se pri startu)
      </span>
    );
  }
  return (
    <span className="text-[10px] text-indigo-300 border border-indigo-500/20 px-2 py-0.5 rounded">
      {FIELD_LABELS[field] || field}: podešeno
    </span>
  );
}

export function CredentialsSecurityPanel({
  credentialsSecurity,
}: {
  credentialsSecurity?: CredentialsSecurityMap | null;
}) {
  if (!credentialsSecurity) return null;

  const anyKeyring = Object.values(credentialsSecurity).some((s) => s.keyring_available);
  const anyPlainJson = Object.entries(credentialsSecurity).some(([, svc]) =>
    Object.values(svc.fields).some((f) => f.in_config_json && f.configured)
  );

  return (
    <div className="glass-panel p-6 rounded-xl border border-glass flex flex-col gap-4 glow-emerald-card glow-card-premium">
      <div className="flex items-center gap-2">
        <KeyRound className="w-5 h-5 text-emerald-400" />
        <h3 className="font-extrabold text-base text-white">Sigurnost naloga (keyring)</h3>
      </div>
      <p className="text-xs text-text-secondary m-0 leading-relaxed">
        Lozinke i tokeni plaćenih pretplata čuvaju se u{" "}
        <strong className="text-white">Windows Credential Manager</strong>
        {anyKeyring ? "" : " (keyring biblioteka nije dostupna — proverite pip install keyring)"}.
        U fajlu <code className="font-mono text-emerald-300/90">~/.videodownload/config.json</code> ostaju
        samo email, username i market.
      </p>
      {anyPlainJson && (
        <div className="text-[11px] text-amber-300 bg-amber-500/10 border border-amber-500/25 rounded-lg px-3 py-2 flex items-start gap-2">
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
          Pronađene su stare vrednosti u config.json — restartujte aplikaciju da se prebace u keyring.
        </div>
      )}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {Object.entries(credentialsSecurity).map(([svc, info]) => (
          <div
            key={svc}
            className="p-3 rounded-lg bg-black/30 border border-white/[0.04] flex flex-col gap-2"
          >
            <span className="text-xs font-bold text-white">{SERVICE_LABELS[svc] || svc}</span>
            <div className="flex flex-wrap gap-1.5">
              {Object.entries(info.fields).map(([field, st]) => (
                <span key={field}>{fieldBadge(field, st)}</span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export function WvdInstallerPanel({
  deviceFound,
  onInstalled,
  showToast,
}: {
  deviceFound?: boolean;
  onInstalled?: () => void;
  showToast: (msg: string, type?: "success" | "error" | "info") => void;
}) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [discovering, setDiscovering] = useState(false);
  const [installing, setInstalling] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [b64, setB64] = useState("");
  const [discovered, setDiscovered] = useState<{ path: string; size: number; is_canonical?: boolean }[]>([]);

  const refreshDiscover = useCallback(async () => {
    setDiscovering(true);
    try {
      const r = await apiFetch("/api/drm/wvd/discover");
      const d = await r.json();
      if (r.ok) setDiscovered(d.files || []);
      else showToast(d.detail || "Pretraga nije uspela", "error");
    } catch (e: unknown) {
      showToast(e instanceof Error ? e.message : "Greška", "error");
    } finally {
      setDiscovering(false);
    }
  }, [showToast]);

  const runAutoInstall = async () => {
    setInstalling(true);
    try {
      const r = await apiFetch("/api/drm/wvd/auto-install", { method: "POST" });
      const d = await r.json();
      if (r.ok) {
        showToast(d.message || "device.wvd instaliran.", "success");
        onInstalled?.();
      } else showToast(d.detail || "Auto-instalacija nije uspela", "error");
    } catch (e: unknown) {
      showToast(e instanceof Error ? e.message : "Greška", "error");
    } finally {
      setInstalling(false);
    }
  };

  const runUpload = async (file: File) => {
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const r = await apiFetch("/api/drm/wvd/upload", { method: "POST", body: fd });
      const d = await r.json();
      if (r.ok) {
        showToast(d.message || "Upload uspešan.", "success");
        setB64("");
        onInstalled?.();
      } else showToast(d.detail || "Upload nije uspeo", "error");
    } catch (e: unknown) {
      showToast(e instanceof Error ? e.message : "Greška", "error");
    } finally {
      setUploading(false);
    }
  };

  const runBase64Install = async () => {
    if (!b64.trim()) {
      showToast("Nalepite base64 sadržaj device.wvd.", "error");
      return;
    }
    setInstalling(true);
    try {
      const r = await apiFetch("/api/drm/wvd/install-base64", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ base64: b64.trim() }),
      });
      const d = await r.json();
      if (r.ok) {
        showToast(d.message || "WVD instaliran.", "success");
        setB64("");
        onInstalled?.();
      } else showToast(d.detail || "Instalacija nije uspela", "error");
    } catch (e: unknown) {
      showToast(e instanceof Error ? e.message : "Greška", "error");
    } finally {
      setInstalling(false);
    }
  };

  return (
    <div className="glass-panel p-6 rounded-xl border border-glass flex flex-col gap-4 glow-violet-card glow-card-premium">
      <div className="flex items-center gap-2 flex-wrap justify-between">
        <div className="flex items-center gap-2">
          <Shield className="w-5 h-5 text-violet-400" />
          <h3 className="font-extrabold text-base text-white">device.wvd — automatska instalacija</h3>
        </div>
        <span
          className={`text-[10px] font-bold px-2 py-0.5 rounded border ${
            deviceFound
              ? "text-emerald-400 border-emerald-500/30 bg-emerald-500/10"
              : "text-red-400 border-red-500/30 bg-red-500/10"
          }`}
        >
          {deviceFound ? "CDM pronađen" : "CDM nedostaje"}
        </span>
      </div>
      <p className="text-xs text-text-secondary m-0 leading-relaxed">
        Umesto ručnog kopiranja putanje, aplikacija može sama pronaći validan{" "}
        <code className="font-mono text-violet-300">.wvd</code> fajl, instalirati ga u{" "}
        <code className="font-mono text-violet-300">~/.videodownload/device.wvd</code> i učitati CDM.
        Ako ste iz alata dobili <strong className="text-white">base64</strong> dump, nalepite ga ispod.
      </p>

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={runAutoInstall}
          disabled={installing || uploading}
          className="btn btn-premium-primary text-xs gap-1.5"
        >
          {installing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Wand2 className="w-4 h-4" />}
          Auto-instaliraj (pronađi na disku)
        </button>
        <button
          type="button"
          onClick={refreshDiscover}
          disabled={discovering}
          className="btn btn-premium-secondary text-xs"
        >
          {discovering ? <Loader2 className="w-4 h-4 animate-spin" /> : "Lista pronađenih"}
        </button>
        <button
          type="button"
          onClick={() => fileRef.current?.click()}
          disabled={uploading}
          className="btn btn-premium-secondary text-xs gap-1.5"
        >
          {uploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
          Upload .wvd fajl
        </button>
        <input
          ref={fileRef}
          type="file"
          accept=".wvd"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) runUpload(f);
            e.target.value = "";
          }}
        />
      </div>

      {discovered.length > 0 && (
        <ul className="text-[10px] font-mono text-text-muted flex flex-col gap-1 m-0 pl-4 list-disc max-h-28 overflow-y-auto">
          {discovered.map((f) => (
            <li key={f.path} className={f.is_canonical ? "text-emerald-400" : ""}>
              {f.path} ({f.size} B){f.is_canonical ? " — kanonski" : ""}
            </li>
          ))}
        </ul>
      )}

      <div>
        <label className="text-xs text-text-muted">Base64 sadržaj device.wvd (paste iz export alata)</label>
        <textarea
          value={b64}
          onChange={(e) => setB64(e.target.value)}
          rows={3}
          placeholder="Nalepite base64 ovde..."
          className="mt-1.5 py-2 px-3 bg-black/40 border border-glass text-white rounded w-full font-mono text-[10px]"
        />
        <button
          type="button"
          onClick={runBase64Install}
          disabled={installing || !b64.trim()}
          className="btn btn-premium-secondary text-xs mt-2"
        >
          Instaliraj iz base64
        </button>
      </div>
    </div>
  );
}

export function SessionConsoleScriptHint({ service }: { service: string }) {
  const script = SESSION_CONSOLE_SCRIPTS[service];
  if (!script) return null;

  const copyCode = () => {
    navigator.clipboard.writeText(script.code);
  };

  return (
    <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-4 flex flex-col gap-2">
      <div className="font-extrabold text-amber-400 text-sm flex items-center gap-2">
        <CheckCircle2 className="w-4 h-4" />
        Konzola — {script.title} (1 sekunda)
      </div>
      <ol className="list-decimal pl-5 text-xs text-text-secondary m-0 gap-1 flex flex-col">
        <li>Otvorite sajt servisa i F12 → Console (samo ako ne koristite Tampermonkey).</li>
        <li>Nalepite kod — šalje token direktno u aplikaciju (bez copy-paste u UI).</li>
      </ol>
      <pre
        className="p-3 bg-black/60 rounded border border-glass font-mono text-[10px] text-amber-300 overflow-x-auto cursor-pointer m-0"
        onClick={copyCode}
        title="Klik za kopiranje"
      >
        {script.code}
      </pre>
    </div>
  );
}
