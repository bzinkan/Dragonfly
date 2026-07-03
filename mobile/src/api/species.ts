import { apiRequest } from "@/src/api/client";

// ---------------------------------------------------------------------------
// GET /v1/species/{taxon_id}
//
// Factual "about this species" sheet served from the backend's cached
// iNaturalist taxon payload. `summary` is iNat's Wikipedia extract today;
// a future reviewed kid-blurb overrides it server-side without changing
// this contract. `facts_available: false` means iNat was unreachable and
// the species wasn't cached yet -- render nothing, never an error.
// ---------------------------------------------------------------------------

export type SpeciesFacts = {
  taxon_id: number;
  common_name: string | null;
  scientific_name: string | null;
  rank: string | null;
  iconic_taxon: string | null;
  summary: string | null;
  wikipedia_url: string | null;
  observations_worldwide: number | null;
  conservation_status: string | null;
  facts_available: boolean;
};

export function getSpeciesFacts(taxonId: number): Promise<SpeciesFacts> {
  return apiRequest<SpeciesFacts>(`/v1/species/${taxonId}`);
}
