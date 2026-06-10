import { Zap, Tv, Film, Play, Radio, Clapperboard, Server, Shield, Settings, Info } from "lucide-react";

// Service metadata for sidebar
export const SERVICE_META = [
  { id: "dashboard", label: "Pametno Preuzimanje", icon: Zap,         colorClass: "text-amber-400",   activeBg: "bg-amber-500",  activeGlow: "rgba(251,191,36,0.3)"  },
  { id: "voyo",     label: "Voyo",                 icon: Tv,           colorClass: "service-voyo",     activeBg: "bg-orange-600", activeGlow: "rgba(249,115,22,0.3)"  },
  { id: "hrti",     label: "HRTi Catalog",         icon: Film,         colorClass: "service-hrti",     activeBg: "bg-cyan-600",   activeGlow: "rgba(6,182,212,0.3)"   },
  { id: "eon",      label: "EON TV",               icon: Play,         colorClass: "service-eon",      activeBg: "bg-emerald-600",activeGlow: "rgba(16,185,129,0.3)"  },
  { id: "rts",      label: "RTS Planeta",          icon: Radio,        colorClass: "service-rts",      activeBg: "bg-rose-600",   activeGlow: "rgba(244,63,94,0.3)"   },
  { id: "hbo",      label: "HBO Max",              icon: Clapperboard, colorClass: "service-hbo",      activeBg: "bg-purple-600", activeGlow: "rgba(147,51,234,0.3)"  },
  { id: "iptv",     label: "IPTV Server",          icon: Server,       colorClass: "text-blue-400",    activeBg: "bg-blue-600",   activeGlow: "rgba(59,130,246,0.3)"  },
  { id: "drm",      label: "DRM / Widevine",       icon: Shield,       colorClass: "text-violet-400",  activeBg: "bg-violet-600", activeGlow: "rgba(139,92,246,0.3)"  },
  { id: "settings", label: "Postavke",             icon: Settings,     colorClass: "text-text-muted",  activeBg: "bg-indigo-600", activeGlow: "rgba(99,102,241,0.3)"  },
  { id: "about",    label: "O Aplikaciji",         icon: Info,         colorClass: "text-pink-400",    activeBg: "bg-pink-600",   activeGlow: "rgba(236,72,153,0.3)"  },
];

// Queue service helpers
export const QUEUE_SERVICE_PILL_CLASS: Record<string, string> = {
  voyo:       "queue-pill-voyo",
  hrti:       "queue-pill-hrti",
  eon:        "queue-pill-eon",
  rts:        "queue-pill-rts",
  rtsplaneta: "queue-pill-rts",
  hbomax:     "queue-pill-hbomax",
};
export const QUEUE_CARD_BORDER_CLASS: Record<string, string> = {
  voyo:       "queue-card-voyo",
  hrti:       "queue-card-hrti",
  eon:        "queue-card-eon",
  rts:        "queue-card-rts",
  rtsplaneta: "queue-card-rts",
  hbomax:     "queue-card-hbomax",
};
