import {
  decideSanctuary3D,
  MAX_GL_CRASHES,
} from "@/src/sanctuary3d/flagDecision";

const ON = {
  buildFlagEnabled: true,
  screenReaderEnabled: false,
  simpleViewPreferred: false,
  crashCount: 0,
};

describe("decideSanctuary3D", () => {
  it("renders 3D when the build flag is on and nothing objects", () => {
    expect(decideSanctuary3D(ON)).toBe(true);
  });

  it("is hard-gated by the build flag", () => {
    expect(decideSanctuary3D({ ...ON, buildFlagEnabled: false })).toBe(false);
  });

  it("falls back to 2D for screen-reader users", () => {
    expect(decideSanctuary3D({ ...ON, screenReaderEnabled: true })).toBe(false);
  });

  it("respects the Simple view preference", () => {
    expect(decideSanctuary3D({ ...ON, simpleViewPreferred: true })).toBe(false);
  });

  it("pins 2D once the crash latch reaches the limit", () => {
    expect(decideSanctuary3D({ ...ON, crashCount: MAX_GL_CRASHES - 1 })).toBe(true);
    expect(decideSanctuary3D({ ...ON, crashCount: MAX_GL_CRASHES })).toBe(false);
    expect(decideSanctuary3D({ ...ON, crashCount: MAX_GL_CRASHES + 5 })).toBe(false);
  });

  it("runtime conditions can only turn 3D off, never on", () => {
    expect(
      decideSanctuary3D({
        buildFlagEnabled: false,
        screenReaderEnabled: false,
        simpleViewPreferred: false,
        crashCount: 0,
      }),
    ).toBe(false);
  });
});
