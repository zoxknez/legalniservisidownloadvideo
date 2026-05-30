import { useCallback, useState } from "react";
import { apiFetch, parseApiError } from "../../lib/api";
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
  const [rtsSubmitting, setRtsSubmitting] = useState(false);

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
    if (rtsSubmitting || !rtsTarget.trim()) return;
    setRtsSubmitting(true);
    try {
      const res = await apiFetch(`/api/rts/download`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          target_url: rtsTarget.trim(),
          start_ep: rtsStartEp ? parseInt(rtsStartEp, 10) : null,
          end_ep: rtsEndEp ? parseInt(rtsEndEp, 10) : null,
          verbose: rtsVerbose,
        }),
      });
      if (res.ok) {
        showToast("RTS Planeta preuzimanje dodato!");
        setRtsTarget("");
      } else {
        const msg = await parseApiError(res, "Greška pri slanju zadatka");
        showToast(msg, "error");
      }
    } catch (e: unknown) {
      showToast(errorMessage(e, "Greška na serveru"), "error");
    } finally {
      setRtsSubmitting(false);
    }
  }, [rtsEndEp, rtsStartEp, rtsSubmitting, rtsTarget, rtsVerbose, showToast]);

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
    rtsSubmitting,
    fetchRtsVideoInfo,
    startRtsDownload,
  };
}

export type RtsSlice = ReturnType<typeof useRts>;
