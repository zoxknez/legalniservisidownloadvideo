import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "../../lib/api";
import { fetchUserscriptText } from "../../lib/bridge";
import { errorMessage } from "../../utils/logUtils";
import type { SniffedItemEntry, SnifferCapture, SnifferReadyEntry } from "../../types/app";
import type { ShowToastFn } from "../domainTypes";

export interface UseSnifferApplyTargets {
  setActiveTab: (tab: string) => void;
  setHboDirectMode: (value: boolean) => void;
  setHboManifestUrl: (value: string) => void;
  setHboLicenseUrl: (value: string) => void;
  setHboDirectTitle: (value: string) => void;
  setEonTarget: (value: string) => void;
}

export interface UseSnifferOptions {
  showToast: ShowToastFn;
  applyTargets: UseSnifferApplyTargets;
}

export function useSniffer({ showToast, applyTargets }: UseSnifferOptions) {
  const [sniffedItems, setSniffedItems] = useState<Record<string, SniffedItemEntry>>({});
  const [latestSniffed, setLatestSniffed] = useState<SnifferCapture | null>(null);
  const [showSnifferToast, setShowSnifferToast] = useState(false);
  const [snifferScriptCopied, setSnifferScriptCopied] = useState(false);
  const [userscriptPreview, setUserscriptPreview] = useState("");
  const [snifferAutoDownload, setSnifferAutoDownload] = useState(true);
  const [snifferReady, setSnifferReady] = useState<Record<string, SnifferReadyEntry>>({});
  const [snifferDownloading, setSnifferDownloading] = useState<string | null>(null);

  const fetchSnifferCaptures = useCallback(async () => {
    try {
      const res = await apiFetch("/api/sniffer/captures");
      if (!res.ok) return;
      const data = await res.json();
      if (data.auto_download !== undefined) {
        setSnifferAutoDownload(Boolean(data.auto_download));
      }
      const captures: Array<{
        service: string;
        manifest_url?: string;
        license_url?: string;
        headers?: Record<string, string>;
        title?: string;
        ready?: boolean;
      }> = data.captures || [];
      if (!captures.length) return;

      const readyMap: Record<string, SnifferReadyEntry> = {};
      const itemsMap: Record<string, SniffedItemEntry> = {};

      for (const capture of captures) {
        const svc = capture.service;
        if (!svc) continue;
        itemsMap[svc] = {
          manifestUrl: capture.manifest_url,
          licenseUrl: capture.license_url,
          headers: capture.headers,
          title: capture.title,
        };
        if (capture.ready) {
          readyMap[svc] = capture as SnifferReadyEntry;
        }
      }
      setSniffedItems((prev) => ({ ...prev, ...itemsMap }));
      setSnifferReady((prev) => ({ ...prev, ...readyMap }));
    } catch (e) {
      console.error("Failed to restore sniffer captures:", e);
    }
  }, []);

  useEffect(() => {
    void fetchSnifferCaptures();
    void fetchUserscriptText()
      .then(setUserscriptPreview)
      .catch(() => setUserscriptPreview(""));
  }, [fetchSnifferCaptures]);

  const applySniffedResource = useCallback(
    (service: string) => {
      const item = sniffedItems[service];
      if (!item) return;

      if (service === "hbomax" || service === "hbo") {
        applyTargets.setHboDirectMode(true);
        if (item.manifestUrl) applyTargets.setHboManifestUrl(item.manifestUrl);
        if (item.licenseUrl) applyTargets.setHboLicenseUrl(item.licenseUrl);
        if (item.title) applyTargets.setHboDirectTitle(item.title);
        applyTargets.setActiveTab("hbo");
        showToast("⚡ HBO Max Bypass polja popunjena!", "success");
      } else if (service === "eon") {
        applyTargets.setEonTarget(item.manifestUrl || "");
        applyTargets.setActiveTab("eon");
        showToast("⚡ EON manifest URL postavljen — proverite license u sniffer panelu.", "info");
      } else {
        showToast(`✓ ${service} resursi detektovani u snifferu.`, "info");
      }
      setShowSnifferToast(false);
    },
    [applyTargets, showToast, sniffedItems],
  );

  const downloadSnifferCapture = useCallback(
    async (service: string, auto = false) => {
      setSnifferDownloading(service);
      try {
        const res = await apiFetch("/api/sniffer/download", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ service }),
        });
        const data = await res.json();
        if (res.ok) {
          showToast(
            auto
              ? `⚡ Auto-preuzimanje pokrenuto: ${data.title || service}`
              : `Preuzimanje pokrenuto: ${data.title || service}`,
            "success",
          );
          setShowSnifferToast(false);
        } else {
          showToast(data.detail || "Sniffer download nije uspeo.", "error");
        }
      } catch (e) {
        showToast(errorMessage(e, "Greška na serveru"), "error");
      } finally {
        setSnifferDownloading(null);
      }
    },
    [showToast],
  );

  const saveSnifferAutoDownload = useCallback(
    async (enabled: boolean) => {
      setSnifferAutoDownload(enabled);
      try {
        await apiFetch("/api/config", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ sniffer: { auto_download: enabled } }),
        });
        showToast(
          enabled ? "Auto-preuzimanje sniffera uključeno." : "Auto-preuzimanje sniffera isključeno.",
          "info",
        );
      } catch {
        showToast("Greška pri čuvanju sniffer podešavanja.", "error");
      }
    },
    [showToast],
  );

  return {
    sniffedItems,
    setSniffedItems,
    latestSniffed,
    setLatestSniffed,
    showSnifferToast,
    setShowSnifferToast,
    snifferScriptCopied,
    setSnifferScriptCopied,
    userscriptPreview,
    setUserscriptPreview,
    snifferAutoDownload,
    setSnifferAutoDownload,
    snifferReady,
    setSnifferReady,
    snifferDownloading,
    setSnifferDownloading,
    fetchSnifferCaptures,
    applySniffedResource,
    downloadSnifferCapture,
    saveSnifferAutoDownload,
  };
}

export type SnifferSlice = ReturnType<typeof useSniffer>;
