import type { AnimationClip, AnimationFrame } from "../../lib/api";

export function playbackOrder(frameCount: number, loopMode: AnimationClip["loop_mode"]): number[] {
  const forward = Array.from({ length: frameCount }, (_, index) => index);
  if (loopMode !== "ping_pong" || frameCount < 3) return forward;
  return [...forward, ...forward.slice(1, -1).reverse()];
}

export function frameAtTime(frames: AnimationFrame[], loopMode: AnimationClip["loop_mode"], elapsedMs: number): number {
  if (frames.length === 0) return -1;
  const order = playbackOrder(frames.length, loopMode);
  const total = order.reduce((sum, index) => sum + frames[index].duration_ms, 0);
  if (total <= 0) return 0;
  let remaining = loopMode === "once"
    ? Math.min(Math.max(0, elapsedMs), total - 1)
    : Math.max(0, elapsedMs) % total;
  for (const index of order) {
    remaining -= frames[index].duration_ms;
    if (remaining < 0) return index;
  }
  return order[order.length - 1];
}
