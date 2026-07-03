import {
  conservationLabel,
  factsAreEmpty,
  worldwideLine,
} from "@/src/observation/speciesFactsLogic";

describe("worldwideLine", () => {
  it("formats large counts with grouping", () => {
    expect(worldwideLine(2412345)).toBe("Spotted 2,412,345 times around the world!");
  });

  it("says nothing for tiny counts", () => {
    expect(worldwideLine(3)).toBeNull();
    expect(worldwideLine(99)).toBeNull();
  });

  it("says nothing when the count is missing", () => {
    expect(worldwideLine(null)).toBeNull();
  });
});

describe("conservationLabel", () => {
  it("title-cases iNat status names", () => {
    expect(conservationLabel("least concern")).toBe("Least Concern");
    expect(conservationLabel("endangered")).toBe("Endangered");
  });

  it("passes through null/empty", () => {
    expect(conservationLabel(null)).toBeNull();
    expect(conservationLabel("")).toBeNull();
  });
});

describe("factsAreEmpty", () => {
  it("is empty when nothing is renderable", () => {
    expect(
      factsAreEmpty({
        summary: null,
        observations_worldwide: 12, // below the fun-fact floor
        conservation_status: null,
        scientific_name: null,
      }),
    ).toBe(true);
  });

  it("is not empty when any fact renders", () => {
    expect(
      factsAreEmpty({
        summary: "A bird.",
        observations_worldwide: null,
        conservation_status: null,
        scientific_name: null,
      }),
    ).toBe(false);
    expect(
      factsAreEmpty({
        summary: null,
        observations_worldwide: 5000,
        conservation_status: null,
        scientific_name: null,
      }),
    ).toBe(false);
  });
});
