/**
 * Pure presentation rules for the species facts card. Kept out of the
 * component so jest can pin them without a renderer.
 */

/**
 * The "spotted worldwide" fun-fact line. Tiny counts aren't a fun fact
 * (and can make a rare find feel unloved), so below 100 we say nothing.
 * en-US grouping keeps output deterministic across devices and tests.
 */
export function worldwideLine(count: number | null): string | null {
  if (count === null || count < 100) return null;
  return `Spotted ${count.toLocaleString("en-US")} times around the world!`;
}

/** "least concern" -> "Least Concern" for the conservation chip. */
export function conservationLabel(statusName: string | null): string | null {
  if (!statusName) return null;
  return statusName.replace(/\b\w/g, (c) => c.toUpperCase());
}

/**
 * True when the sheet has nothing renderable -- the card hides entirely
 * rather than showing an empty "About this species" header.
 */
export function factsAreEmpty(facts: {
  summary: string | null;
  observations_worldwide: number | null;
  conservation_status: string | null;
  scientific_name: string | null;
}): boolean {
  return (
    facts.summary === null &&
    worldwideLine(facts.observations_worldwide) === null &&
    facts.conservation_status === null &&
    facts.scientific_name === null
  );
}
