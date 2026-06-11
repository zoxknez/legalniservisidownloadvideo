import { useCallback, useEffect, useState } from "react";
import { apiFetch, parseApiError } from "../../lib/api";
import { errorMessage } from "../../utils/logUtils";
import type { VoyoProfile } from "../../types/app";
import type { ShowToastFn } from "../domainTypes";

export function useVoyoProfiles(
  authenticated: boolean,
  showToast: ShowToastFn,
) {
  const [profiles, setProfiles] = useState<VoyoProfile[]>([]);
  const [activeProfileId, setActiveProfileId] = useState(0);
  const [loading, setLoading] = useState(false);
  const [switching, setSwitching] = useState(false);

  const refreshProfiles = useCallback(async () => {
    if (!authenticated) {
      setProfiles([]);
      setActiveProfileId(0);
      return;
    }
    setLoading(true);
    try {
      const res = await apiFetch("/api/voyo/profiles");
      if (res.ok) {
        const data = await res.json();
        setProfiles(data.profiles ?? []);
        setActiveProfileId(data.active_profile_id ?? 0);
      } else {
        setProfiles([]);
      }
    } catch {
      setProfiles([]);
    } finally {
      setLoading(false);
    }
  }, [authenticated]);

  useEffect(() => {
    void refreshProfiles();
  }, [refreshProfiles]);

  const selectProfile = useCallback(
    async (profileId: number) => {
      if (!profileId || profileId === activeProfileId) return;
      setSwitching(true);
      try {
        const res = await apiFetch("/api/voyo/profile", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ profile_id: profileId }),
        });
        if (res.ok) {
          setActiveProfileId(profileId);
          showToast("Voyo profil je promenjen.", "success");
        } else {
          const msg = await parseApiError(res, "Promena profila nije uspela.");
          showToast(msg, "error");
        }
      } catch (e) {
        showToast(errorMessage(e, "Greška pri promeni profila"), "error");
      } finally {
        setSwitching(false);
      }
    },
    [activeProfileId, showToast],
  );

  return {
    voyoProfiles: profiles,
    voyoActiveProfileId: activeProfileId,
    voyoProfilesLoading: loading,
    voyoProfileSwitching: switching,
    refreshVoyoProfiles: refreshProfiles,
    selectVoyoProfile: selectProfile,
  };
}
