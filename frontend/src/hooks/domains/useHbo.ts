import { useCallback, useState } from "react";
import { apiFetch } from "../../lib/api";
import { errorMessage } from "../../utils/logUtils";
import type { ShowToastFn } from "../domainTypes";

export interface UseHboOptions {
  showToast: ShowToastFn;
}

export function useHbo({ showToast }: UseHboOptions) {
  const [hboMarket, setHboMarket] = useState("emea");
  const [hboTarget, setHboTarget] = useState("");
  const [hboSubs, setHboSubs] = useState("sr,hr,mk,bs,sl");
  const [hboDirectMode, setHboDirectMode] = useState(false);
  const [hboManifestUrl, setHboManifestUrl] = useState("");
  const [hboLicenseUrl, setHboLicenseUrl] = useState("");
  const [hboDirectTitle, setHboDirectTitle] = useState("");
  const [hboDirectSubs, setHboDirectSubs] = useState("sr,hr,mk,bs,sl");

  const startHboLogin = useCallback(async () => {
    try {
      const res = await apiFetch(`/api/hbo/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ market: hboMarket }),
      });
      if (res.ok) {
        showToast("Pokrenuta HBO Max prijava! Otvorite terminal/logs da vidite kod.");
      } else {
        showToast("Neuspešno pokretanje prijave", "error");
      }
    } catch (e: unknown) {
      showToast(errorMessage(e, "Greška na serveru"), "error");
    }
  }, [hboMarket, showToast]);

  const startHboDownload = useCallback(async () => {
    try {
      const res = await apiFetch(`/api/hbo/download`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ video_id: hboTarget, subs: hboSubs }),
      });
      if (res.ok) {
        showToast("HBO Max preuzimanje pokrenuto!");
        setHboTarget("");
      } else {
        showToast("Greška pri slanju zadatka", "error");
      }
    } catch (e: unknown) {
      showToast(errorMessage(e, "Greška na serveru"), "error");
    }
  }, [hboSubs, hboTarget, showToast]);

  const startHboDirectDownload = useCallback(async () => {
    if (!hboManifestUrl.trim() || !hboLicenseUrl.trim()) {
      showToast("Unesite i Manifest URL i License URL", "error");
      return;
    }
    try {
      const res = await apiFetch(`/api/hbo/download-direct`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          manifest_url: hboManifestUrl.trim(),
          license_url: hboLicenseUrl.trim(),
          title: hboDirectTitle.trim(),
          subs: hboDirectSubs,
        }),
      });
      if (res.ok) {
        showToast("HBO Max Direct preuzimanje pokrenuto! ✓");
        setHboManifestUrl("");
        setHboLicenseUrl("");
        setHboDirectTitle("");
      } else {
        const err = await res.json().catch(() => ({}));
        showToast(err?.detail || "Greška pri slanju zadatka", "error");
      }
    } catch (e: unknown) {
      showToast(errorMessage(e, "Greška na serveru"), "error");
    }
  }, [hboDirectSubs, hboDirectTitle, hboLicenseUrl, hboManifestUrl, showToast]);

  return {
    hboMarket,
    setHboMarket,
    hboTarget,
    setHboTarget,
    hboSubs,
    setHboSubs,
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
    startHboLogin,
    startHboDownload,
    startHboDirectDownload,
  };
}

export type HboSlice = ReturnType<typeof useHbo>;
