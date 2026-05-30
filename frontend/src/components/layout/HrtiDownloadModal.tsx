import {
  Download,
  Loader2,
} from "lucide-react";
import { useHrtiTab } from "../../hooks/domains/useHrtiTab";

export function HrtiDownloadModal() {
  const {
    confirmHrtiDownload,
    hrtiModal,
    hrtiModalTitle,
    hrtiSubmitting,
    setHrtiModal,
    setHrtiModalTitle,
  } = useHrtiTab();
  if (!hrtiModal) return null;
  return (
  <div className="inline-modal-overlay" onClick={(e) => e.target === e.currentTarget && !hrtiSubmitting && setHrtiModal(null)}>
    <div className="inline-modal">
      <div className="flex items-center gap-3 mb-5">
        <div style={{width:40,height:40,borderRadius:10,background:"linear-gradient(135deg,#06b6d4,#0284c7)",display:"flex",alignItems:"center",justifyContent:"center",flexShrink:0}}>
          <Download style={{width:18,height:18,color:"white"}} />
        </div>
        <div>
          <h3 className="font-extrabold text-white text-base">Preuzimanje HRTi sadržaja</h3>
          <p className="text-text-muted text-xs mt-0.5">Možete promeniti naziv fajla pre preuzimanja</p>
        </div>
      </div>
      <div className="mb-4">
        <label>Naziv fajla (opciono)</label>
        <input
          type="text"
          value={hrtiModalTitle}
          onChange={(e) => setHrtiModalTitle(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !hrtiSubmitting && confirmHrtiDownload()}
          placeholder={hrtiModal.title}
          disabled={hrtiSubmitting}
          autoFocus
        />
        <p className="text-[10px] text-text-muted mt-1.5">Ostavite prazno za automatski naziv: <span className="text-indigo-400 font-mono">{hrtiModal.title}</span></p>
      </div>
      <div className="flex gap-3 justify-end">
        <button
          onClick={() => { setHrtiModal(null); setHrtiModalTitle(""); }}
          className="btn btn-secondary text-sm py-2 px-5"
          disabled={hrtiSubmitting}
        >
          Otkaži
        </button>
        <button
          onClick={confirmHrtiDownload}
          className="btn btn-primary text-sm py-2 px-5"
          disabled={hrtiSubmitting}
        >
          {hrtiSubmitting ? (
            <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Slanje...</>
          ) : (
            <><Download style={{width:14,height:14}} /> Preuzmi</>
          )}
        </button>
      </div>
    </div>
  </div>
  );
}
