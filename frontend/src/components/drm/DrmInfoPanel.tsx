import { Info, AlertTriangle, ChevronRight } from "lucide-react";

interface DrmRecommendationsProps {
  recommendations: string[];
}

export function DrmRecommendations({ recommendations }: DrmRecommendationsProps) {
  if (!recommendations.length) return null;
  return (
    <div className="glass-panel p-5 rounded-xl border border-amber-500/20 bg-amber-500/5">
      <h3 className="text-sm font-bold text-amber-300 mb-3 flex items-center gap-2">
        <AlertTriangle className="w-4 h-4" /> Preporuke
      </h3>
      <ul className="flex flex-col gap-2">
        {recommendations.map((r, i) => (
          <li key={i} className="flex items-start gap-2 text-xs text-amber-200/80">
            <ChevronRight className="w-3.5 h-3.5 flex-shrink-0 mt-0.5 text-amber-400" />
            {r}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function DrmSecurityLevels() {
  return (
    <div className="glass-panel p-5 rounded-xl border border-glass">
      <h3 className="text-sm font-bold text-white mb-3 flex items-center gap-2">
        <Info className="w-4 h-4 text-slate-400" /> L1 vs L3 – Objašnjenje
      </h3>
      <div className="flex flex-col gap-2 text-[11px] text-text-muted leading-relaxed">
        {[
          {level:"L1",color:"#10b981",desc:"Widevine se izvršava u hardverskom TEE (Trusted Execution Environment). Ključevi nikad ne napuštaju sigurni čip. Podržava 4K HDR streams. Zahtijeva certifikovani uređaj (Android TEE, Qualcomm SPE...)."},
          {level:"L2",color:"#f59e0b",desc:"Kriptografija u TEE, ali dekodiranje može biti u softveru. Rijetko korišten, prelazni nivo."},
          {level:"L3",color:"#6366f1",desc:"Potpuno softverski CDM – pokreće se u user-space procesu. Dostupan na svim PC-evima. Ograničen na 1080p/SDR za većinu servisa. Keybox je zaštićen softverski."},
        ].map(({level,color,desc}) => (
          <div key={level} className="rounded-lg p-2.5 border" style={{background:`${color}0d`,borderColor:`${color}30`}}>
            <span className="font-extrabold text-xs" style={{color}}>{level}  </span>
            {desc}
          </div>
        ))}
      </div>
    </div>
  );
}
