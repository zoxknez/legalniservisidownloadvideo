import {
  Info,
} from "lucide-react";
import { cssVars } from "../../utils/cssVars";

export function AboutTab() {
  return (
<div key="about" className="tab-content tab-content-about max-w-4xl mx-auto flex flex-col gap-6">
    <div className="tab-page-header tab-header-about mb-4" style={{ background: "linear-gradient(135deg, #ec4899, #be185d)" }}>
      <div className="tab-page-header-icon animate-pulse" style={{ background: "rgba(255, 255, 255, 0.15)", width: 40, height: 40, borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center" }}>
        <Info style={{ width: 20, height: 20, color: "white" }} />
      </div>
      <div style={{ flex: 1 }}>
        <h2 className="text-2xl font-extrabold text-white mb-1 flex items-center gap-2.5">
          O Aplikaciji
        </h2>
        <p className="text-pink-100 text-xs">Informacije o platformi, tehnologijama i autoru projekta.</p>
      </div>
    </div>

    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
      
      {/* Creator Card */}
      <div className="md:col-span-1 glass-panel p-6 rounded-xl border border-glass glow-pink-card glow-card-premium flex flex-col items-center text-center gap-4 relative overflow-hidden">
        <div className="console-scanline" />
        <div className="w-20 h-20 rounded-full bg-gradient-to-tr from-pink-500 via-rose-500 to-indigo-500 p-1 shadow-lg shadow-pink-500/20 group relative">
          <div className="w-full h-full rounded-full bg-[#12131b] flex items-center justify-center text-2xl font-black text-white group-hover:scale-105 transition-transform">
            o0o
          </div>
        </div>

        <div>
          <h3 className="font-extrabold text-lg text-white m-0 tracking-wide">o0o0o0o</h3>
          <span className="text-[10px] font-black tracking-wider text-pink-400 uppercase bg-pink-500/10 px-2 py-0.5 rounded border border-pink-500/20 mt-1 inline-block">
            Glavni Programer
          </span>
        </div>

        <div className="w-full border-t border-white/[0.04] pt-4 mt-2">
          <a
            href="https://github.com/zoxknez"
            target="_blank"
            rel="noopener noreferrer"
            className="btn btn-premium-primary w-full py-3 text-xs font-bold text-white text-center flex items-center justify-center gap-2"
            style={cssVars({
              "--btn-grad-start": "#ec4899",
              "--btn-grad-end": "#be185d",
              "--btn-glow": "rgba(236,72,153,0.25)",
              "--btn-glow-hover": "rgba(236,72,153,0.45)"
            })}
          >
            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
              <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
            </svg>
            Poseti Moj GitHub
          </a>
        </div>
      </div>

      {/* System Specs & Description */}
      <div className="md:col-span-2 flex flex-col gap-6">
        

        {/* Key Technologies */}
        <div className="glass-panel p-6 rounded-xl border border-glass flex flex-col gap-4 animate-slide">
          <h3 className="font-extrabold text-base text-white border-b border-white/[0.04] pb-2">Elitne Tehnologije Platforme</h3>
          
          <div className="flex flex-col gap-3">
            {[
              {
                title: "Widevine DRM CENC Dekripcija",
                desc: "Automatska ekstrakcija Widevine PSSH manifesta, prefetch provider sertifikata i licencna razmena u realnom vremenu uz in-memory dekodiranje audio i video segmenata.",
                color: "text-violet-400"
              },
              {
                title: "GPU Hardverska Kompresija (HEVC & AV1)",
                desc: "Integrisan i optimizovan FFmpeg pipeline koji koristi snagu vaše grafičke kartice (NVIDIA NVENC, Intel QSV, AMD AMF) za automatsku 30-50% uštedu diska bez gubitka kvaliteta.",
                color: "text-indigo-400"
              },
              {
                title: "Mrežna Mimikrija & Chrome TLS Fingerprint",
                desc: "Imitacija originalnih zaglavlja, extension redosleda i TLS cipher suite-ova (JA3) najnovijih verzija Chrome pretraživača za apsolutno zaobilaženje Cloudflare, Akamai i ostalih bot-zaštita.",
                color: "text-pink-400"
              },
              {
                title: "Lokalni IPTV HLS Proxy & DVR",
                desc: "Pretvara vašu aplikaciju u kućni striming centar koji dešifruje i distribuira EON TV / HRTi live kanale direktno na VLC, Kodi ili Smart TV, uz automatizovano EPG-sinhronizovano snimanje.",
                color: "text-blue-400"
              }
            ].map((tech, i) => (
              <div key={i} className="flex gap-3 items-start border-b border-white/[0.02] last:border-b-0 pb-2.5 last:pb-0">
                <div className="w-5 h-5 rounded-full bg-white/[0.04] flex items-center justify-center text-[10px] font-black text-text-muted flex-shrink-0 mt-0.5">
                  {i + 1}
                </div>
                <div>
                  <h4 className={`font-bold text-xs ${tech.color} m-0`}>{tech.title}</h4>
                  <p className="text-[11px] text-text-secondary leading-normal mt-1 m-0">{tech.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

      </div>
    </div>
  </div>
  );
}
