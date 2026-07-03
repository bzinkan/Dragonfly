import { useQuery } from "@tanstack/react-query";

import { getSpeciesFacts } from "@/src/api/species";

/**
 * Species fact sheet for an identified observation. The server-side
 * cache is fresh-indefinitely (ADR 0006: taxa change rarely), so a
 * session-long client cache is fine.
 */
export function useSpeciesFacts(taxonId: number | null) {
  return useQuery({
    queryKey: ["species-facts", taxonId],
    queryFn: () => {
      if (taxonId === null) throw new Error("useSpeciesFacts disabled without taxonId");
      return getSpeciesFacts(taxonId);
    },
    enabled: taxonId !== null,
    staleTime: Infinity,
  });
}
