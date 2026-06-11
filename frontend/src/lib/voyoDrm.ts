/** Voyo DRM: catalog hint vs stream probe (authoritative). */

export interface VoyoDrmFields {
  drm?: boolean;
  drm_hint?: boolean;
  drm_blocking?: boolean;
  streamable?: boolean;
  probe_ok?: boolean;
  stream_reason?: string;
}

export function voyoCatalogDrmHint(item: VoyoDrmFields): boolean {
  return !!(item.drm_hint ?? item.drm);
}

export function voyoIsHardBlocked(item: VoyoDrmFields): boolean {
  if (item.drm_blocking) return true;
  if (item.probe_ok && item.streamable === false) return true;
  return false;
}

export function voyoIsSoftHint(item: VoyoDrmFields, ignoreCatalogDrmHint: boolean): boolean {
  if (ignoreCatalogDrmHint) return false;
  if (voyoIsHardBlocked(item)) return false;
  return voyoCatalogDrmHint(item);
}

export function defaultVoyoEpisodeIds<T extends VoyoDrmFields & { id: number }>(
  episodes: T[],
  ignoreCatalogDrmHint: boolean,
): number[] {
  return episodes
    .filter((ep) => !voyoIsHardBlocked(ep) && (ignoreCatalogDrmHint || !voyoCatalogDrmHint(ep)))
    .map((ep) => ep.id);
}

export function defaultSmartEpisodeIds(
  episodes: (VoyoDrmFields & { id: number | string })[],
  ignoreCatalogDrmHint: boolean,
): (number | string)[] {
  return episodes
    .filter((ep) => !voyoIsHardBlocked(ep) && (ignoreCatalogDrmHint || !voyoCatalogDrmHint(ep)))
    .map((ep) => ep.id);
}

export const VOYO_HARD_BLOCK_MSG = "Stream nije dostupan za preuzimanje (Widevine ili nedostupan URL).";
export const VOYO_HINT_MSG =
  "Označeno kao zaštićeno u katalogu — stream će biti proveren pri preuzimanju (AES-128 je podržan).";
