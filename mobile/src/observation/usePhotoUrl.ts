import { useQuery } from "@tanstack/react-query";

import { getPhotoUrl } from "@/src/api/photos";
import { useAuthSession } from "@/src/auth/session";

export const PHOTO_URL_STALE_MS = 40_000;
export const PHOTO_URL_GC_MS = 60_000;

/**
 * Signed GET URL for one photo, cached under the server's 60-second
 * SAS TTL so a rendered <Image> never holds a URL that expires mid-load,
 * and scrolling back to a card within the window reuses the same URL
 * (which also lets the native image cache hit instead of refetching
 * bytes -- the SAS query string is part of the cache key).
 *
 * refetchInterval keeps long-mounted screens honest: gcTime only bounds
 * UNOBSERVED queries, and RN has no window-focus refetch, so a Field Journal tab
 * left open would otherwise hold a URL past expiry forever. The interval
 * only fires for observed (visible) queries, so cost stays bounded.
 * Callers must still gate rendering on isUrlUsable(expires_at) -- a
 * cache hit can be already-expired at mount, and the swap-in of fresh
 * data is a background refetch.
 */
export function usePhotoUrl(photoId: string, enabled: boolean) {
  const ownerUserId = useAuthSession((state) =>
    state.status === "authenticated" ? state.user.id : null,
  );
  return useQuery({
    queryKey: ["photo-url", ownerUserId ?? "anonymous", photoId],
    queryFn: ({ signal }) => getPhotoUrl(photoId, signal),
    enabled: enabled && ownerUserId != null,
    staleTime: PHOTO_URL_STALE_MS,
    gcTime: PHOTO_URL_GC_MS,
    refetchInterval: PHOTO_URL_STALE_MS,
    // No retry override: inherit the client default, which already
    // retries network/5xx and skips 4xx.
  });
}
