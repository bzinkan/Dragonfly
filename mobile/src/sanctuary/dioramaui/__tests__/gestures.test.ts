import {
  classifyRelease,
  TAP_MAX_SPEED,
  TAP_SLOP,
} from "@/src/sanctuary/dioramaui/gestures";

describe("classifyRelease", () => {
  it("a still finger is a tap", () => {
    expect(classifyRelease({ dx: 0, dy: 0, vx: 0, vy: 0 })).toBe("tap");
  });

  it("small slow movement is still a tap (kid fingers wobble)", () => {
    expect(classifyRelease({ dx: 3, dy: -4, vx: 0.05, vy: -0.05 })).toBe("tap");
  });

  it("large movement is a pan regardless of speed", () => {
    expect(classifyRelease({ dx: 40, dy: 0, vx: 0, vy: 0 })).toBe("pan");
  });

  it("D4 finding a: a fast fling with tiny movement is a PAN, not a tap", () => {
    // Short-lived fling: only 5dp of travel but released at high speed.
    // Slop alone would have called this a tap.
    expect(classifyRelease({ dx: 5, dy: 0, vx: 1.2, vy: 0 })).toBe("pan");
  });

  it("uses both axes for movement and speed", () => {
    // 6dp on each axis = 8.49dp total: over the slop diagonally.
    expect(classifyRelease({ dx: 6, dy: 6, vx: 0, vy: 0 })).toBe("pan");
    // 0.25 dp/ms on each axis = 0.35 total: over the speed cap diagonally.
    expect(classifyRelease({ dx: 0, dy: 0, vx: 0.25, vy: 0.25 })).toBe("pan");
  });

  it("boundary values classify as pan (thresholds are exclusive)", () => {
    expect(classifyRelease({ dx: TAP_SLOP, dy: 0, vx: 0, vy: 0 })).toBe("pan");
    expect(classifyRelease({ dx: 0, dy: 0, vx: TAP_MAX_SPEED, vy: 0 })).toBe(
      "pan",
    );
  });
});
