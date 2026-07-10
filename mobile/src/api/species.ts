import { apiRequest } from "@/src/api/client";

// ---------------------------------------------------------------------------
// GET /v1/species/{taxon_id}
//
// Factual "about this species" sheet served from the project catalog.
// `summary` and `wikipedia_url` remain nullable compatibility fields and must
// stay null until a separately approved reviewed-kid-blurb pipeline exists.
// The mobile UI deliberately ignores both fields even if an older response
// sends them. There is no live third-party fallback on this request path.
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
