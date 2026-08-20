import { describe, expect, it } from "vitest";
import { activityLabel, activityOf } from "./makeoverActivity";

describe("activityOf", () => {
  it("maps every stage phase onto the dock LED vocabulary", () => {
    expect(activityOf("propose")).toBe("idle");
    expect(activityOf("proposing")).toBe("proposing");
    expect(activityOf("proposed")).toBe("ready");
    expect(activityOf("locking")).toBe("idle");
    expect(activityOf("error")).toBe("error");
  });
});

describe("activityLabel", () => {
  it("spells out every lit state and stays quiet when idle", () => {
    expect(activityLabel("idle")).toBeNull();
    expect(activityLabel("proposing")).toBe("proposing…");
    expect(activityLabel("ready")).toBe("proposal ready");
    expect(activityLabel("error")).toBe("proposal failed");
  });
});
