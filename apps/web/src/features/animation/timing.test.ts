import { describe, expect, it } from "vitest";

import type { AnimationFrame } from "../../lib/api";
import { frameAtTime, playbackOrder } from "./timing";

const frames = [100, 250, 150].map((duration_ms, frame_index) => ({ duration_ms, frame_index })) as AnimationFrame[];

describe("animation timing", () => {
  it("uses frame durations and wraps at the clip end", () => {
    expect(frameAtTime(frames, "loop", 0)).toBe(0);
    expect(frameAtTime(frames, "loop", 100)).toBe(1);
    expect(frameAtTime(frames, "loop", 349)).toBe(1);
    expect(frameAtTime(frames, "loop", 350)).toBe(2);
    expect(frameAtTime(frames, "loop", 500)).toBe(0);
    expect(frameAtTime(frames, "once", 900)).toBe(2);
  });

  it("bounces through intermediate frames", () => {
    expect(playbackOrder(3, "ping_pong")).toEqual([0, 1, 2, 1]);
    expect(frameAtTime(frames, "ping_pong", 500)).toBe(1);
    expect(frameAtTime([], "loop", 100)).toBe(-1);
  });
});
