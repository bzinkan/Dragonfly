import {
  FIRST_FRAME_TIMEOUT_MS,
  isStrikeTransition,
  reduceWatchdog,
  type WatchdogEvent,
  type WatchdogPhase,
} from "@/src/sanctuary/dioramaui/watchdog";

describe("reduceWatchdog", () => {
  it("passes when the first frame beats the timer", () => {
    expect(reduceWatchdog("waiting", "first-frame")).toBe("passed");
    // The late timer firing afterwards is a no-op.
    expect(reduceWatchdog("passed", "timeout")).toBe("passed");
  });

  it("trips when the timer beats the first frame", () => {
    expect(reduceWatchdog("waiting", "timeout")).toBe("tripped");
    // A frame after tripping cannot un-trip (the strike already counted).
    expect(reduceWatchdog("tripped", "first-frame")).toBe("tripped");
  });

  it("a crash trips from any live phase", () => {
    expect(reduceWatchdog("waiting", "crash")).toBe("tripped");
    // Crashes AFTER a healthy first frame still count.
    expect(reduceWatchdog("passed", "crash")).toBe("tripped");
  });

  it("tripped is absorbing", () => {
    for (const event of ["first-frame", "timeout", "crash"] as const) {
      expect(reduceWatchdog("tripped", event)).toBe("tripped");
    }
  });

  it("has a total transition table", () => {
    const phases: WatchdogPhase[] = ["waiting", "passed", "tripped"];
    const events: WatchdogEvent[] = ["first-frame", "timeout", "crash"];
    for (const phase of phases) {
      for (const event of events) {
        expect(phases).toContain(reduceWatchdog(phase, event));
      }
    }
  });

  it("records exactly one strike per mount", () => {
    // Replay a nasty sequence: timeout, then a late frame, then a crash.
    // Only the FIRST transition into tripped is a strike.
    const events: WatchdogEvent[] = ["timeout", "first-frame", "crash"];
    let phase: WatchdogPhase = "waiting";
    let strikes = 0;
    for (const event of events) {
      const next = reduceWatchdog(phase, event);
      if (isStrikeTransition(phase, next)) strikes++;
      phase = next;
    }
    expect(strikes).toBe(1);
    expect(phase).toBe("tripped");
  });

  it("a healthy session records zero strikes", () => {
    const events: WatchdogEvent[] = ["first-frame", "timeout"];
    let phase: WatchdogPhase = "waiting";
    let strikes = 0;
    for (const event of events) {
      const next = reduceWatchdog(phase, event);
      if (isStrikeTransition(phase, next)) strikes++;
      phase = next;
    }
    expect(strikes).toBe(0);
    expect(phase).toBe("passed");
  });

  it("gives slow devices a real chance at the first frame", () => {
    // 2-core/2GB emulators recorded 35 pictures in D4 well under this;
    // the timeout guards hangs, not slowness.
    expect(FIRST_FRAME_TIMEOUT_MS).toBeGreaterThanOrEqual(5000);
  });
});
