import { useCallback, useEffect, useState } from "react";
import { apiFetch, parseApiError } from "../../lib/api";
import { errorMessage } from "../../utils/logUtils";
import type { SkyShowtimeSeriesInfo } from "../../types/app";
import type { ShowToastFn } from "../domainTypes";

export interface SkyShowtimeAuthStatus {
  authenticated: boolean;
  token_path: string;
  token_expiry: string;
  territory: string;
}

export interface UseSkyShowtimeOptions {
  showToast: ShowToastFn;
}

async function pollAuthRefresh(
  refreshAuth: () => void,
  attempts = 8,
  intervalMs = 2000,
): Promise<void> {
  for (let i = 0; i < attempts; i += 1) {
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
    refreshAuth();
  }
}

export function useSkyshowtime({ showToast }: UseSkyShowtimeOptions) {
  const [skyshowtimeTarget, setSkyshowtimeTarget] = useState("");
  const [skyshowtimeSeason, setSkyshowtimeSeason] = useState("");
  const [skyshowtimeStartEp, setSkyshowtimeStartEp] = useState("1");
  const [skyshowtimeEndEp, setSkyshowtimeEndEp] = useState("");
  const [skyshowtimeVcodec, setSkyshowtimeVcodec] = useState("H264");
  const [skyshowtimeQuality, setSkyshowtimeQuality] = useState("SDR");
  const [skyshowtimeAudioLang, setSkyshowtimeAudioLang] = useState("en");
  const [skyshowtimeDirectMode, setSkyshowtimeDirectMode] = useState(false);
  const [skyshowtimeManifestUrl, setSkyshowtimeManifestUrl] = useState("");
  const [skyshowtimeLicenseUrl, setSkyshowtimeLicenseUrl] = useState("");
  const [skyshowtimeLicenseToken, setSkyshowtimeLicenseToken] = useState("");
  const [skyshowtimeDirectTitle, setSkyshowtimeDirectTitle] = useState("");
  const [skyshowtimeSeriesData, setSkyshowtimeSeriesData] = useState<SkyShowtimeSeriesInfo | null>(null);
  const [selectedSkyshowtimeEpisodes, setSelectedSkyshowtimeEpisodes] = useState<string[]>([]);
  const [skyshowtimeSearching, setSkyshowtimeSearching] = useState(false);
  const [skyshowtimeSubmitting, setSkyshowtimeSubmitting] = useState(false);
  const [skyshowtimeAuth, setSkyshowtimeAuth] = useState<SkyShowtimeAuthStatus | null>(null);

  const refreshAuth = useCallback(() => {
    apiFetch("/api/skyshowtime/status")
      .then((r) => r.json())
      .then((data) => setSkyshowtimeAuth(data))
      .catch(() => {});
  }, []);

  useEffect(() => {
    refreshAuth();
  }, [refreshAuth]);

  const searchSkyshowtimeSeries = useCallback(async () => {
    const target = skyshowtimeTarget.trim();
    if (!target || skyshowtimeSearching) return;
    setSkyshowtimeSearching(true);
    try {
      const res = await apiFetch(`/api/skyshowtime/resolve?target=${encodeURIComponent(target)}`);
      const data = await res.json();
      if (res.ok && data.success) {
        setSkyshowtimeSeriesData(data);
        setSelectedSkyshowtimeEpisodes(data.episodes.map((ep: { id: string }) => ep.id));
        if (data.series_url) {
          setSkyshowtimeTarget(data.series_url);
        }
        showToast(`Serija pronađena: ${data.title}`, "success");
      } else {
        setSkyshowtimeSeriesData(null);
        setSelectedSkyshowtimeEpisodes([]);
        showToast(await parseApiError(res, "Serija nije pronađena"), "error");
      }
    } catch (e: unknown) {
      showToast(errorMessage(e, "Greška na serveru"), "error");
    } finally {
      setSkyshowtimeSearching(false);
    }
  }, [skyshowtimeTarget, skyshowtimeSearching, showToast]);

  const startSkyshowtimeBrowserSync = useCallback(async () => {
    if (skyshowtimeSubmitting) return;
    setSkyshowtimeSubmitting(true);
    try {
      const res = await apiFetch("/api/skyshowtime/sync-browser", { method: "POST" });
      const data = await res.json();
      if (res.ok) {
        setSkyshowtimeAuth(data);
        showToast(data.message || "SkyShowtime sesija sinhronizovana!", "success");
      } else {
        showToast(await parseApiError(res, "Sinhronizacija nije uspela"), "error");
      }
    } catch (e: unknown) {
      showToast(errorMessage(e, "Greška na serveru"), "error");
    } finally {
      setSkyshowtimeSubmitting(false);
    }
  }, [skyshowtimeSubmitting, showToast]);

  const startSkyshowtimeLogin = useCallback(async (cookiesText?: string, cookies?: Record<string, string>) => {
    if (skyshowtimeSubmitting) return;
    setSkyshowtimeSubmitting(true);
    try {
      const res = await apiFetch("/api/skyshowtime/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cookies_text: cookiesText, cookies }),
      });
      if (res.ok) {
        showToast("Pokrenuta prijava na SkyShowtime! Proverite konzolu logova.");
        void pollAuthRefresh(refreshAuth);
      } else {
        showToast(await parseApiError(res, "Neuspešno pokretanje prijave"), "error");
      }
    } catch (e: unknown) {
      showToast(errorMessage(e, "Greška na serveru"), "error");
    } finally {
      setSkyshowtimeSubmitting(false);
    }
  }, [skyshowtimeSubmitting, showToast, refreshAuth]);

  const startSkyshowtimeDirectDownload = useCallback(async () => {
    if (!skyshowtimeManifestUrl.trim() || !skyshowtimeLicenseUrl.trim() || skyshowtimeSubmitting) return;
    setSkyshowtimeSubmitting(true);
    try {
      const res = await apiFetch("/api/skyshowtime/download-direct", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          manifest_url: skyshowtimeManifestUrl.trim(),
          license_url: skyshowtimeLicenseUrl.trim(),
          license_token: skyshowtimeLicenseToken.trim() || undefined,
          title: skyshowtimeDirectTitle.trim(),
          vcodec: skyshowtimeVcodec,
          quality: skyshowtimeQuality,
          audio_lang: skyshowtimeAudioLang || undefined,
        }),
      });
      if (res.ok) {
        showToast("SkyShowtime direktno preuzimanje pokrenuto!");
        setSkyshowtimeManifestUrl("");
        setSkyshowtimeLicenseUrl("");
        setSkyshowtimeLicenseToken("");
        setSkyshowtimeDirectTitle("");
      } else {
        showToast(await parseApiError(res, "Greška pri slanju zadatka"), "error");
      }
    } catch (e: unknown) {
      showToast(errorMessage(e, "Greška na serveru"), "error");
    } finally {
      setSkyshowtimeSubmitting(false);
    }
  }, [
    skyshowtimeManifestUrl,
    skyshowtimeLicenseUrl,
    skyshowtimeLicenseToken,
    skyshowtimeDirectTitle,
    skyshowtimeVcodec,
    skyshowtimeQuality,
    skyshowtimeAudioLang,
    skyshowtimeSubmitting,
    showToast,
  ]);

  const startSkyshowtimeDownload = useCallback(async () => {
    if (!skyshowtimeTarget.trim() || skyshowtimeSubmitting) return;
    setSkyshowtimeSubmitting(true);
    try {
      const payload: Record<string, unknown> = {
        url: skyshowtimeTarget.trim(),
        vcodec: skyshowtimeVcodec,
        quality: skyshowtimeQuality,
        audio_lang: skyshowtimeAudioLang || undefined,
      };

      if (skyshowtimeSeriesData && selectedSkyshowtimeEpisodes.length > 0) {
        payload.episode_refs = selectedSkyshowtimeEpisodes;
      } else {
        if (skyshowtimeSeason.trim()) {
          payload.season = parseInt(skyshowtimeSeason, 10);
        }
        if (skyshowtimeStartEp.trim()) {
          payload.start_ep = parseInt(skyshowtimeStartEp, 10);
        }
        if (skyshowtimeEndEp.trim()) {
          payload.end_ep = parseInt(skyshowtimeEndEp, 10);
        }
      }

      const res = await apiFetch("/api/skyshowtime/download", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        const data = await res.json();
        showToast(
          data.queued
            ? `SkyShowtime: ${data.queued} epizoda u redu!`
            : "SkyShowtime preuzimanje pokrenuto!",
        );
        if (!skyshowtimeSeriesData) {
          setSkyshowtimeTarget("");
        }
      } else {
        showToast(await parseApiError(res, "Greška pri slanju zadatka"), "error");
      }
    } catch (e: unknown) {
      showToast(errorMessage(e, "Greška na serveru"), "error");
    } finally {
      setSkyshowtimeSubmitting(false);
    }
  }, [
    skyshowtimeTarget,
    skyshowtimeSeason,
    skyshowtimeStartEp,
    skyshowtimeEndEp,
    skyshowtimeVcodec,
    skyshowtimeQuality,
    skyshowtimeAudioLang,
    skyshowtimeSeriesData,
    selectedSkyshowtimeEpisodes,
    skyshowtimeSubmitting,
    showToast,
  ]);

  const pasteSkyshowtimeTarget = useCallback(async () => {
    try {
      const text = await navigator.clipboard.readText();
      const trimmed = text.trim();
      if (trimmed) {
        setSkyshowtimeTarget(trimmed);
        setSkyshowtimeSeriesData(null);
        setSelectedSkyshowtimeEpisodes([]);
        showToast("Link zalepljen!", "success");
      } else {
        showToast("Clipboard je prazan.", "error");
      }
    } catch {
      showToast("Dozvola za clipboard nije odobrena.", "error");
    }
  }, [showToast]);

  return {
    skyshowtimeTarget,
    setSkyshowtimeTarget,
    skyshowtimeSeason,
    setSkyshowtimeSeason,
    skyshowtimeStartEp,
    setSkyshowtimeStartEp,
    skyshowtimeEndEp,
    setSkyshowtimeEndEp,
    skyshowtimeVcodec,
    setSkyshowtimeVcodec,
    skyshowtimeQuality,
    setSkyshowtimeQuality,
    skyshowtimeAudioLang,
    setSkyshowtimeAudioLang,
    skyshowtimeDirectMode,
    setSkyshowtimeDirectMode,
    skyshowtimeManifestUrl,
    setSkyshowtimeManifestUrl,
    skyshowtimeLicenseUrl,
    setSkyshowtimeLicenseUrl,
    skyshowtimeLicenseToken,
    setSkyshowtimeLicenseToken,
    skyshowtimeDirectTitle,
    setSkyshowtimeDirectTitle,
    skyshowtimeSeriesData,
    setSkyshowtimeSeriesData,
    selectedSkyshowtimeEpisodes,
    setSelectedSkyshowtimeEpisodes,
    skyshowtimeSearching,
    skyshowtimeSubmitting,
    skyshowtimeAuth,
    refreshAuth,
    searchSkyshowtimeSeries,
    startSkyshowtimeBrowserSync,
    startSkyshowtimeLogin,
    startSkyshowtimeDownload,
    startSkyshowtimeDirectDownload,
    pasteSkyshowtimeTarget,
  };
}

export type SkyshowtimeSlice = ReturnType<typeof useSkyshowtime>;
