import { useCallback, useState } from "react";
import { apiFetch } from "../../lib/api";
import { errorMessage } from "../../utils/logUtils";
import type { RtsVideoInfo } from "../../types/app";
import type { ShowToastFn } from "../domainTypes";

export interface UseRtsOptions {
  showToast: ShowToastFn;
}

export function useRts({ showToast }: UseRtsOptions) {
  const [rtsEmail, setRtsEmail] = useState("");
  const [rtsPassword, setRtsPassword] = useState("");
  const [showRtsPass, setShowRtsPass] = useState(false);

  const [rtsTarget, setRtsTarget] = useState("");
  const [rtsStartEp, setRtsStartEp] = useState("");
  const [rtsEndEp, setRtsEndEp] = useState("");
  const [rtsVerbose, setRtsVerbose] = useState(false);
  const [rtsVideoInfo, setRtsVideoInfo] = useState<RtsVideoInfo | null>(null);
  const [rtsInfoLoading, setRtsInfoLoading] = useState(false);

  const fetchRtsVideoInfo = useCallback(async (url: string) => {
    const val = url.trim();
    if (!val || !val.includes("rtsplaneta")) {
      setRtsVideoInfo(null);
      return;
    }
    setRtsInfoLoading(true);
    try {
      const res = await apiFetch(`/api/rts/video-info?url=${encodeURIComponent(val)}`);
      if (res.ok) {
        setRtsVideoInfo(await res.json());
      } else {
        setRtsVideoInfo(null);
      }
    } catch {
      setRtsVideoInfo(null);
    } finally {
      setRtsInfoLoading(false);
    }
  }, []);

  const startRtsDownload = useCallback(async () => {
    try {
      const res = await apiFetch(`/api/rts/download`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          target_url: rtsTarget,
          start_ep: rtsStartEp ? parseInt(rtsStartEp, 10) : null,
          end_ep: rtsEndEp ? parseInt(rtsEndEp, 10) : null,
          verbose: rtsVerbose,
        }),
      });
      if (res.ok) {
        showToast("RTS Planeta preuzimanje dodato!");
        setRtsTarget("");
      } else {
        showToast("Greška pri slanju zadatka", "error");
      }
    } catch (e: unknown) {
      showToast(errorMessage(e, "Greška na serveru"), "error");
    }
  }, [rtsEndEp, rtsStartEp, rtsTarget, rtsVerbose, showToast]);

  return {
    rtsEmail,
    setRtsEmail,
    rtsPassword,
    setRtsPassword,
    showRtsPass,
    setShowRtsPass,
    rtsTarget,
    setRtsTarget,
    rtsStartEp,
    setRtsStartEp,
    rtsEndEp,
    setRtsEndEp,
    rtsVerbose,
    setRtsVerbose,
    rtsVideoInfo,
    setRtsVideoInfo,
    rtsInfoLoading,
    setRtsInfoLoading,
    fetchRtsVideoInfo,
    startRtsDownload,
  };
}

export type RtsSlice = ReturnType<typeof useRts>;
