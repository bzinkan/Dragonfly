import type { ObservationReward, RewardType } from "@/src/api/observations";
import type { ProgressItem } from "@/src/api/expeditions";
import {
  activeProgress,
  expeditionRewardTarget,
  filterByEnvironment,
  nextIncompleteStep,
  nextObjective,
  progressLabel,
  selectExpeditionRewards,
  selectSanctuaryRewards,
  splitProgress,
} from "@/src/expeditions/logic";

function reward(type: RewardType, title: string = type): ObservationReward {
  return { type, title, detail: "", icon: "icon-key", weight: 1, payload: {} };
}

function expeditionReward(
  type: RewardType,
  expeditionId: string,
): ObservationReward {
  return {
    ...reward(type),
    payload: { expedition_id: expeditionId },
  };
}

describe("selectExpeditionRewards", () => {
  it("returns [] when rewards is undefined", () => {
    expect(selectExpeditionRewards(undefined)).toEqual([]);
  });

  it("returns [] when rewards is empty", () => {
    expect(selectExpeditionRewards([])).toEqual([]);
  });

  it("keeps only expedition_step / expedition_complete from a mixed list", () => {
    const mixed = [
      reward("first_find"),
      reward("expedition_step"),
      reward("world_unlock"),
      reward("expedition_complete"),
      reward("rarity_tier"),
    ];
    expect(selectExpeditionRewards(mixed).map((r) => r.type)).toEqual([
      "expedition_step",
      "expedition_complete",
    ]);
  });

  it("preserves dispatcher order", () => {
    const mixed = [
      reward("expedition_step", "step one"),
      reward("repeat_find"),
      reward("expedition_step", "step two"),
    ];
    expect(selectExpeditionRewards(mixed).map((r) => r.title)).toEqual([
      "step one",
      "step two",
    ]);
  });
});

describe("selectSanctuaryRewards", () => {
  it("returns [] when rewards is undefined", () => {
    expect(selectSanctuaryRewards(undefined)).toEqual([]);
  });

  it("returns [] when rewards is empty", () => {
    expect(selectSanctuaryRewards([])).toEqual([]);
  });

  it("keeps only world_unlock / world_evolution from a mixed list", () => {
    const mixed = [
      reward("expedition_step"),
      reward("world_unlock"),
      reward("first_find"),
      reward("world_evolution"),
    ];
    expect(selectSanctuaryRewards(mixed).map((r) => r.type)).toEqual([
      "world_unlock",
      "world_evolution",
    ]);
  });
});

describe("nextIncompleteStep", () => {
  const step = (id: string, completed_at: string | null) => ({
    id,
    completed_at,
  });

  it("returns null for an empty array", () => {
    expect(nextIncompleteStep([])).toBeNull();
  });

  it("returns null when every step is complete", () => {
    const steps = [
      step("a", "2026-06-01T00:00:00Z"),
      step("b", "2026-06-02T00:00:00Z"),
    ];
    expect(nextIncompleteStep(steps)).toBeNull();
  });

  it("returns the first incomplete step in content order", () => {
    const steps = [
      step("a", "2026-06-01T00:00:00Z"),
      step("b", null),
      step("c", null),
    ];
    expect(nextIncompleteStep(steps)?.id).toBe("b");
  });
});

describe("filterByEnvironment", () => {
  const exp = (id: string, environments: string[]) => ({ id, environments });

  it("returns [] for an empty list", () => {
    expect(filterByEnvironment([], "yard")).toEqual([]);
  });

  it("returns every item when env is null", () => {
    const items = [exp("a", ["yard"]), exp("b", ["park", "street"])];
    expect(filterByEnvironment(items, null)).toEqual(items);
  });

  it("keeps only items tagged with the selected environment", () => {
    const items = [exp("a", ["yard", "park"]), exp("b", ["street"])];
    expect(filterByEnvironment(items, "park").map((e) => e.id)).toEqual(["a"]);
  });

  it('includes "other" items for any environment', () => {
    const items = [exp("a", ["other"]), exp("b", ["school"])];
    expect(filterByEnvironment(items, "yard").map((e) => e.id)).toEqual(["a"]);
    expect(filterByEnvironment(items, "school").map((e) => e.id)).toEqual([
      "a",
      "b",
    ]);
  });

  it("preserves input order", () => {
    const items = [
      exp("a", ["yard"]),
      exp("b", ["other"]),
      exp("c", ["yard", "park"]),
    ];
    expect(filterByEnvironment(items, "yard").map((e) => e.id)).toEqual([
      "a",
      "b",
      "c",
    ]);
  });
});

describe("splitProgress", () => {
  const item = (id: string, completed_at: string | null) => ({
    id,
    completed_at,
  });

  it("returns two empty buckets for an empty list", () => {
    expect(splitProgress([])).toEqual({ inProgress: [], completed: [] });
  });

  it("buckets by completed_at", () => {
    const items = [item("a", null), item("b", "2026-06-01T00:00:00Z")];
    const { inProgress, completed } = splitProgress(items);
    expect(inProgress.map((i) => i.id)).toEqual(["a"]);
    expect(completed.map((i) => i.id)).toEqual(["b"]);
  });

  it("preserves input order within each bucket", () => {
    const items = [
      item("a", "2026-06-01T00:00:00Z"),
      item("b", null),
      item("c", "2026-06-02T00:00:00Z"),
      item("d", null),
    ];
    const { inProgress, completed } = splitProgress(items);
    expect(inProgress.map((i) => i.id)).toEqual(["b", "d"]);
    expect(completed.map((i) => i.id)).toEqual(["a", "c"]);
  });
});

describe("activeProgress", () => {
  function item(id: string, completed_at: string | null = null): ProgressItem {
    return {
      expedition_id: id,
      title: id,
      subtitle: null,
      intro: "",
      outro: "",
      theme: "warmup",
      learning_goal: null,
      difficulty_label: null,
      started_at: "2026-06-01T00:00:00Z",
      completed_at,
      focused_at: null,
      completed_step_count: 0,
      total_step_count: 1,
      steps: [
        {
          id: "s0",
          description: "Find something",
          hint: null,
          tag_prompt: null,
          completed_at: null,
        },
      ],
    };
  }

  it("uses the backend active id when it points at an incomplete expedition", () => {
    const items = [item("newest"), item("focused")];
    expect(activeProgress(items, "focused")?.expedition_id).toBe("focused");
  });

  it("falls back to the first incomplete expedition", () => {
    const items = [item("done", "2026-06-01T01:00:00Z"), item("next")];
    expect(activeProgress(items, null)?.expedition_id).toBe("next");
  });

  it("returns null when every expedition is complete", () => {
    expect(activeProgress([item("done", "2026-06-01T01:00:00Z")], null)).toBeNull();
  });
});

describe("nextObjective / progressLabel", () => {
  it("returns the active incomplete step and compact progress text", () => {
    const progress: ProgressItem = {
      expedition_id: "x",
      title: "Quest",
      subtitle: null,
      intro: "",
      outro: "",
      theme: "warmup",
      learning_goal: null,
      difficulty_label: null,
      started_at: "2026-06-01T00:00:00Z",
      completed_at: null,
      focused_at: null,
      completed_step_count: 1,
      total_step_count: 2,
      steps: [
        {
          id: "a",
          description: "Done",
          hint: null,
          tag_prompt: null,
          completed_at: "2026-06-01T01:00:00Z",
        },
        {
          id: "b",
          description: "Next",
          hint: "Look close",
          tag_prompt: null,
          completed_at: null,
        },
      ],
    };
    expect(nextObjective(progress)?.id).toBe("b");
    expect(progressLabel(progress)).toBe("1 / 2 steps");
  });
});

describe("expeditionRewardTarget", () => {
  it("prefers the focused expedition reward when several advanced", () => {
    const rewards = [
      expeditionReward("expedition_step", "side"),
      expeditionReward("expedition_complete", "focused"),
    ];
    const target = expeditionRewardTarget(rewards, "focused");
    expect(target.primary?.type).toBe("expedition_complete");
    expect(target.expeditionId).toBe("focused");
    expect(target.extraCount).toBe(1);
  });
});
