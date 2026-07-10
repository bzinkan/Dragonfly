import { useQuery } from "@tanstack/react-query";

import { getApiMeta, type ApiMeta } from "@/src/api/meta";

export function photoHelperIsEnabled(meta: ApiMeta | null | undefined): boolean {
  return meta?.capabilities?.observation?.photo_helper_enabled === true;
}

/** Capability reads fail closed: a missing/malformed/unavailable flag hides CV. */
export function useObservationCapabilities() {
  const query = useQuery({
    queryKey: ["meta", "observation-capabilities"],
    queryFn: ({ signal }) => getApiMeta(signal),
    staleTime: 30_000,
    refetchInterval: 30_000,
  });
  return {
    photoHelperEnabled: query.isSuccess && photoHelperIsEnabled(query.data),
    query,
  };
}
