import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { AnimationClip, AnimationFrame, Asset } from "../../lib/api";
import { AnimationTimeline } from "./AnimationTimeline";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const asset: Asset = {
  id: "asset-1", project_id: "project-1", name: "Hero", asset_type: "character",
  style: "eight_bit", width: 16, height: 16, color_mode: "RGBA",
  active_version_id: "version-1", thumbnail_path: "", created_at: "", updated_at: "",
};

describe("AnimationTimeline", () => {
  it("shows the selected clip direction rather than the previous clip value", async () => {
    const clips: AnimationClip[] = [
      { id: "clip-up", asset_id: asset.id, name: "walk", direction: "up", fps: 8,
        loop_mode: "loop", canvas_width: 16, canvas_height: 16 },
      { id: "clip-down", asset_id: asset.id, name: "idle", direction: "down", fps: 8,
        loop_mode: "loop", canvas_width: 16, canvas_height: 16 },
    ];
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = input.toString();
      if (url.endsWith("/asset-1/animations")) return new Response(JSON.stringify(clips));
      if (url.endsWith("/asset-1/versions") || url.endsWith("/frames")) return new Response("[]");
      return new Response("{}", { status: 404 });
    });
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={queryClient}><AnimationTimeline asset={asset} /></QueryClientProvider>);
    await userEvent.click(await screen.findByRole("button", { name: "walk · up" }));
    expect(screen.getByRole("textbox", { name: "Direction" })).toHaveValue("up");
    await userEvent.click(screen.getByRole("button", { name: "idle · down" }));
    expect(screen.getByRole("textbox", { name: "Direction" })).toHaveValue("down");
  });

  it("creates a clip, edits frames, reorders, and toggles onion skin", async () => {
    const user = userEvent.setup();
    const clips: AnimationClip[] = [];
    const frames: AnimationFrame[] = [];
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = input.toString();
      const payload = init?.body ? JSON.parse(init.body as string) as Record<string, unknown> : {};
      if (url.endsWith("/asset-1/versions")) return new Response(JSON.stringify([
        { id: "version-1", version_number: 1 }, { id: "version-2", version_number: 2 },
      ]));
      if (url.endsWith("/asset-1/animations")) {
        if (init?.method === "POST") {
          clips.push({ id: "clip-1", asset_id: "asset-1", name: payload.name as string,
            direction: "down", fps: 8, loop_mode: "loop", canvas_width: 16, canvas_height: 16 });
          return new Response(JSON.stringify(clips[0]), { status: 201 });
        }
        return new Response(JSON.stringify(clips));
      }
      if (url.endsWith("/clip-1/frames")) {
        if (init?.method === "POST") {
          const frame: AnimationFrame = { id: `frame-${frames.length + 1}`, animation_id: "clip-1",
            asset_version_id: payload.asset_version_id as string, frame_index: frames.length,
            duration_ms: 125, offset_x: 0, offset_y: 0, pivot_x: 0, pivot_y: 0, event_name: null };
          frames.push(frame);
          return new Response(JSON.stringify(frame), { status: 201 });
        }
        return new Response(JSON.stringify(frames));
      }
      if (url.endsWith("/duplicate")) {
        const copy = { ...frames[0], id: "frame-2", frame_index: 1 };
        frames.push(copy);
        return new Response(JSON.stringify(copy), { status: 201 });
      }
      if (url.endsWith("/reorder")) {
        const ids = payload.frame_ids as string[];
        frames.sort((left, right) => ids.indexOf(left.id) - ids.indexOf(right.id));
        frames.forEach((frame, index) => { frame.frame_index = index; });
        return new Response(JSON.stringify(frames));
      }
      if (url.endsWith("/frame-1") && init?.method === "PATCH") {
        Object.assign(frames.find((frame) => frame.id === "frame-1")!, payload);
        return new Response(JSON.stringify(frames.find((frame) => frame.id === "frame-1")));
      }
      return new Response("{}", { status: 404 });
    });
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={queryClient}><AnimationTimeline asset={asset} /></QueryClientProvider>);

    await user.type(screen.getByLabelText("Animation name"), "walk");
    await user.click(screen.getByRole("button", { name: "Add clip" }));
    await user.click(await screen.findByRole("button", { name: "walk · down" }));
    await user.click(await screen.findByRole("button", { name: "Add frame" }));
    expect(await screen.findByText("1 · 125ms")).toBeInTheDocument();
    fireEvent.blur(screen.getByLabelText("duration_ms"), { target: { value: "250" } });
    await waitFor(() => expect(frames[0].duration_ms).toBe(250));
    await user.click(screen.getByLabelText("Onion skin"));
    expect(screen.getByLabelText("Onion skin")).toBeChecked();
    await user.click(screen.getByLabelText("Onion skin"));
    expect(screen.getByLabelText("Onion skin")).not.toBeChecked();
    await user.click(screen.getByRole("button", { name: "Duplicate frame" }));
    expect(await screen.findByText("2 · 250ms")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Move right" }));
    await waitFor(() => expect(frames[0].id).toBe("frame-2"));
  });
});
