import { useCallback, useEffect, useState } from "react";
import { apiFetch, parseApiError } from "../../lib/api";
import { errorMessage } from "../../utils/logUtils";
import type { ShowToastFn } from "../domainTypes";

const UUID_RE = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi;

function extractHboVideoId(raw: string): string {
  const trimmed = raw.trim();
  if (/^[0-9a-f]{8}-[0-9a-f]{4}/i.test(trimmed) && !trimmed.includes("/")) {
    return trimmed;
  }
  const uuids = trimmed.match(UUID_RE);
  if (uuids?.length) return uuids[uuids.length - 1];
  return trimmed;
}

export interface HboAuthStatus {
  authenticated: boolean;
  market: string;
  token_path: string;
}

export interface UseHboOptions {
  showToast: ShowToastFn;
}

export function useHbo({ showToast }: UseHboOptions) {
  const [hboMarket, setHboMarket] = useState("emea");
  const [hboTarget, setHboTarget] = useState("");
  const [hboSubs, setHboSubs] = useState("all");
  const [hboAudio, setHboAudio] = useState("all");
  const [hboDirectMode, setHboDirectMode] = useState(false);
  const [hboManifestUrl, setHboManifestUrl] = useState("");
  const [hboLicenseUrl, setHboLicenseUrl] = useState("");
  const [hboDirectTitle, setHboDirectTitle] = useState("");
  const [hboDirectSubs, setHboDirectSubs] = useState("all");
  const [hboDirectAudio, setHboDirectAudio] = useState("all");
  const [hboSubmitting, setHboSubmitting] = useState(false);
  const [hboAuth, setHboAuth] = useState<HboAuthStatus | null>(null);

  useEffect(() => {
    apiFetch("/api/hbo/status")
      .then((r) => r.json())
      .then((data) => setHboAuth(data))
      .catch(() => {});
  }, []);

  const refreshAuth = useCallback(() => {
    apiFetch("/api/hbo/status")
      .then((r) => r.json())
      .then((data) => setHboAuth(data))
      .catch(() => {});
  }, []);

  const startHboLogin = useCallback(async () => {
    if (hboSubmitting) return;
    setHboSubmitting(true);
    try {
      const res = await apiFetch(`/api/hbo/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ market: hboMarket }),
      });
      if (res.ok) {
        showToast("Pokrenuta HBO Max prijava! Otvorite Logs da vidite kod.");
      } else {
        showToast(await parseApiError(res, "Neuspešno pokretanje prijave"), "error");
      }
    } catch (e: unknown) {
      showToast(errorMessage(e, "Greška na serveru"), "error");
    } finally {
      setHboSubmitting(false);
    }
  }, [hboMarket, hboSubmitting, showToast]);

  const startHboDownload = useCallback(async () => {
    const id = extractHboVideoId(hboTarget);
    if (!id || hboSubmitting) return;
    setHboSubmitting(true);
    try {
      const res = await apiFetch(`/api/hbo/download`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          video_id: id,
          subs: hboSubs,
          audio: hboAudio,
          market: hboMarket,
        }),
      });
      if (res.ok) {
        showToast("HBO Max preuzimanje pokrenuto!");
        setHboTarget("");
      } else {
        showToast(await parseApiError(res, "Greška pri slanju zadatka"), "error");
      }
    } catch (e: unknown) {
      showToast(errorMessage(e, "Greška na serveru"), "error");
    } finally {
      setHboSubmitting(false);
    }
  }, [hboAudio, hboMarket, hboSubs, hboSubmitting, hboTarget, showToast]);

  const startHboDirectDownload = useCallback(async () => {
    if (!hboManifestUrl.trim() || !hboLicenseUrl.trim() || hboSubmitting) return;
    setHboSubmitting(true);
    try {
      const res = await apiFetch(`/api/hbo/download-direct`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          manifest_url: hboManifestUrl.trim(),
          license_url: hboLicenseUrl.trim(),
          title: hboDirectTitle.trim(),
          subs: hboDirectSubs,
          audio: hboDirectAudio,
        }),
      });
      if (res.ok) {
        showToast("HBO Max Direct preuzimanje pokrenuto!");
        setHboManifestUrl("");
        setHboLicenseUrl("");
        setHboDirectTitle("");
      } else {
        showToast(await parseApiError(res, "Greška pri slanju zadatka"), "error");
      }
    } catch (e: unknown) {
      showToast(errorMessage(e, "Greška na serveru"), "error");
    } finally {
      setHboSubmitting(false);
    }
  }, [hboDirectAudio, hboDirectSubs, hboDirectTitle, hboLicenseUrl, hboManifestUrl, hboSubmitting, showToast]);

  const pasteHboTarget = useCallback(async () => {
    try {
      const text = await navigator.clipboard.readText();
      const trimmed = text.trim();
      if (trimmed) {
        setHboTarget(trimmed);
        showToast("Link zalepljen!", "success");
      } else {
        showToast("Clipboard je prazan.", "error");
      }
    } catch {
      showToast("Dozvola za clipboard nije odobrena.", "error");
    }
  }, [showToast]);

  return {
    hboMarket,
    setHboMarket,
    hboTarget,
    setHboTarget,
    hboSubs,
    setHboSubs,
    hboAudio,
    setHboAudio,
    hboDirectMode,
    setHboDirectMode,
    hboManifestUrl,
    setHboManifestUrl,
    hboLicenseUrl,
    setHboLicenseUrl,
    hboDirectTitle,
    setHboDirectTitle,
    hboDirectSubs,
    setHboDirectSubs,
    hboDirectAudio,
    setHboDirectAudio,
    hboSubmitting,
    hboAuth,
    refreshAuth,
    pasteHboTarget,
    startHboLogin,
    startHboDownload,
    startHboDirectDownload,
  };
}

export type HboSlice = ReturnType<typeof useHbo>;
