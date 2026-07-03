import {
  galleryCaption,
  isAwaitingModeration,
  isUrlUsable,
  photoDisplayMode,
} from "@/src/observation/galleryLogic";

describe("photoDisplayMode", () => {
  it("shows the image for clean photos", () => {
    expect(photoDisplayMode("clean")).toBe("image");
  });

  it("shows the kid their own photo while moderation is pending", () => {
    expect(photoDisplayMode("pending")).toBe("image");
  });

  it("hides quarantined photos behind a reviewing placeholder", () => {
    expect(photoDisplayMode("quarantine")).toBe("reviewing");
  });

  it("marks rejected photos as removed", () => {
    expect(photoDisplayMode("deleted")).toBe("removed");
  });

  it("fails safe on unknown future statuses", () => {
    expect(photoDisplayMode("archived")).toBe("reviewing");
    expect(photoDisplayMode("")).toBe("reviewing");
  });
});

describe("isAwaitingModeration", () => {
  it("is true only for pending", () => {
    expect(isAwaitingModeration("pending")).toBe(true);
    expect(isAwaitingModeration("clean")).toBe(false);
    expect(isAwaitingModeration("quarantine")).toBe(false);
    expect(isAwaitingModeration("deleted")).toBe(false);
  });
});

describe("isUrlUsable", () => {
  it("accepts a URL with comfortable life left", () => {
    expect(isUrlUsable(new Date(Date.now() + 4 * 60 * 1000).toISOString())).toBe(true);
  });

  it("rejects a URL inside the 30s safety margin", () => {
    expect(isUrlUsable(new Date(Date.now() + 10_000).toISOString())).toBe(false);
  });

  it("rejects an already-expired URL", () => {
    expect(isUrlUsable(new Date(Date.now() - 1000).toISOString())).toBe(false);
  });

  it("rejects garbage timestamps (NaN comparison is false)", () => {
    expect(isUrlUsable("not-a-date")).toBe(false);
  });
});

describe("galleryCaption", () => {
  it("uses the species name when picked", () => {
    expect(galleryCaption("Northern Cardinal")).toBe("Northern Cardinal");
  });

  it("falls back to Mystery find when the kid skipped", () => {
    expect(galleryCaption(null)).toBe("Mystery find");
  });
});
