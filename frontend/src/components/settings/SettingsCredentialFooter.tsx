import type { CSSProperties } from "react";
import { Loader2, LogOut } from "lucide-react";

type SettingsCredentialFooterProps = {
  loginLabel: string;
  onLogin: () => void;
  onClear: () => void;
  loginLoading?: boolean;
  clearLoading?: boolean;
  loginDisabled?: boolean;
  loginStyle?: CSSProperties;
  clearClassName?: string;
};

export function SettingsCredentialFooter({
  loginLabel,
  onLogin,
  onClear,
  loginLoading = false,
  clearLoading = false,
  loginDisabled = false,
  loginStyle,
  clearClassName = "text-text-muted hover:text-rose-400",
}: SettingsCredentialFooterProps) {
  const busy = loginLoading || clearLoading;
  return (
    <div className="flex flex-col gap-2 mt-1">
      <button
        type="button"
        onClick={onLogin}
        disabled={loginDisabled || busy}
        className="btn btn-premium-primary text-xs w-full"
        style={loginStyle}
      >
        {loginLoading ? (
          <span className="flex items-center justify-center gap-2">
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
            Čuvanje…
          </span>
        ) : (
          loginLabel
        )}
      </button>
      <button
        type="button"
        onClick={onClear}
        disabled={busy}
        className={`text-[10px] font-bold flex items-center justify-center gap-1 transition-colors ${clearClassName}`}
      >
        {clearLoading ? (
          <>
            <Loader2 className="w-3 h-3 animate-spin" />
            Brisanje…
          </>
        ) : (
          <>
            <LogOut className="w-3 h-3" />
            Obriši sačuvane kredencijale
          </>
        )}
      </button>
    </div>
  );
}
