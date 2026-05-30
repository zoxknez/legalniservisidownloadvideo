import {
  AlertCircle,
  CheckCircle2,
  Info,
} from "lucide-react";
import { useAppShell } from "../../hooks/domains/useAppShell";

export function AppToast() {
  const { toast, toastKey } = useAppShell();
  if (!toast) return null;
  return (
  <div className={`fixed top-6 right-6 z-50 flex items-center gap-3 px-5 py-4 rounded-lg glass-panel animate-slide overflow-hidden ${
    toast.type === "error" ? "glow-red" : toast.type === "success" ? "glow-emerald" : "glow-indigo"
  }`} style={{paddingBottom: "1.25rem"}}>
    {toast.type === "success" && <CheckCircle2 className="w-5 h-5 text-emerald-400 flex-shrink-0" />}
    {toast.type === "error" && <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0" />}
    {toast.type === "info" && <Info className="w-5 h-5 text-indigo-400 flex-shrink-0" />}
    <span className="text-sm font-medium">{toast.message}</span>
    {/* Progress bar — auto-dismiss indicator */}
    <div key={toastKey} className={`toast-progress toast-progress-${toast.type}`} />
  </div>
  );
}
