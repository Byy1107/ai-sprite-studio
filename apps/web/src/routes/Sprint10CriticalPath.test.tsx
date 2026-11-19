import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";

import { DashboardPage } from "./DashboardPage";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  Reflect.deleteProperty(Image.prototype, "decode");
});

it("completes the mocked UI path from project creation through spritesheet export", async () => {
  const project = {
    id: "project-1", name: "Hero Project", slug: "hero-project", description: "",
    root_path: "workspace/hero-project", schema_version: 1,
    created_at: "2026-11-11T00:00:00Z", updated_at: "2026-11-11T00:00:00Z",
    last_opened_at: null,
  };
  const asset = {
    id: "asset-1", project_id: project.id, name: "Hero", asset_type: "character",
    style: "eight_bit", width: 8, height: 8, color_mode: "RGBA",
    active_version_id: "version-1", thumbnail_path: "assets/hero.png",
    created_at: project.created_at, updated_at: project.updated_at,
  };
  const clip = {
    id: "clip-1", asset_id: asset.id, name: "idle", direction: "down", fps: 8,
    loop_mode: "loop", canvas_width: 8, canvas_height: 8,
  };
  const frame = {
    id: "frame-1", animation_id: clip.id, asset_version_id: "version-1",
    frame_index: 0, duration_ms: 125, offset_x: 0, offset_y: 0,
    pivot_x: 0, pivot_y: 0, event_name: null,
  };
  const exported = {
    id: "export-1", project_id: project.id, asset_id: asset.id,
    format: "spritesheet", preset_id: null, config: {},
    output_path: "exports/sheet.png", checksum: "checksum", status: "succeeded",
    created_at: project.created_at,
  };
  const projects: typeof project[] = [];
  const assets: typeof asset[] = [];
  const clips: typeof clip[] = [];
  const frames: typeof frame[] = [];
  const exports: typeof exported[] = [];
  const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    if (url.endsWith("/projects") && init?.method === "POST") {
      projects.push(project);
      return new Response(JSON.stringify(project), { status: 201 });
    }
    if (url.endsWith("/projects")) return new Response(JSON.stringify(projects));
    if (url.endsWith("/project-1/open")) return new Response(JSON.stringify(project));
    if (url.endsWith("/project-1/assets/import")) {
      assets.push(asset);
      return new Response(JSON.stringify(asset), { status: 201 });
    }
    if (url.endsWith("/project-1/assets")) return new Response(JSON.stringify(assets));
    if (url.endsWith("/asset-1/versions")) return new Response(JSON.stringify([
      { id: "version-1", version_number: 1, source: "import", checksum: "checksum" },
    ]));
    if (url.endsWith("/asset-1/animations") && init?.method === "POST") {
      clips.push(clip);
      return new Response(JSON.stringify(clip), { status: 201 });
    }
    if (url.endsWith("/asset-1/animations")) return new Response(JSON.stringify(clips));
    if (url.endsWith("/clip-1/frames") && init?.method === "POST") {
      frames.push(frame);
      return new Response(JSON.stringify(frame), { status: 201 });
    }
    if (url.endsWith("/clip-1/frames")) return new Response(JSON.stringify(frames));
    if (url.endsWith("/project-1/exports")) return new Response(JSON.stringify(exports));
    if (url.endsWith("/exports") && init?.method === "POST") {
      exports.push(exported);
      return new Response(JSON.stringify(exported), { status: 201 });
    }
    return new Response("[]");
  });
  Object.defineProperty(Image.prototype, "decode", {
    configurable: true, value: vi.fn().mockResolvedValue(undefined),
  });
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({
    drawImage: vi.fn(), clearRect: vi.fn(), putImageData: vi.fn(),
    getImageData: () => ({ width: 8, height: 8, data: new Uint8ClampedArray(8 * 8 * 4) }),
  } as unknown as CanvasRenderingContext2D);
  vi.stubGlobal("ImageData", class {
    constructor(public data: Uint8ClampedArray, public width: number, public height: number) {}
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={queryClient}><DashboardPage /></QueryClientProvider>);
  const user = userEvent.setup();

  await user.click(await screen.findByRole("button", { name: "New project" }));
  await user.type(screen.getByLabelText("Project name"), project.name);
  await user.click(screen.getByRole("button", { name: "Create project" }));
  expect(await screen.findByRole("heading", { name: project.name })).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Open project" }));
  expect(await screen.findByRole("heading", { name: "Asset library" })).toBeInTheDocument();
  await user.type(screen.getByLabelText("Asset name"), asset.name);
  await user.upload(screen.getByLabelText("PNG file"), new File(["png"], "hero.png", { type: "image/png" }));
  fireEvent.submit(screen.getByRole("button", { name: "Import PNG" }).closest("form")!);
  expect(await screen.findByRole("heading", { name: "Moveset · Hero" })).toBeInTheDocument();
  await user.type(screen.getByLabelText("Animation name"), clip.name);
  await user.click(screen.getByRole("button", { name: "Add clip" }));
  expect(await screen.findByRole("button", { name: "idle · down" })).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Add frame" }));
  expect(await screen.findByText("1 · 125ms")).toBeInTheDocument();
  await user.selectOptions(screen.getByLabelText("Export clip"), clip.id);
  await user.click(screen.getByRole("button", { name: "Export sheet + JSON" }));
  expect(await screen.findByRole("link", { name: "JSON" })).toHaveAttribute(
    "href", "/api/v1/exports/export-1/files/json",
  );
  expect(fetchMock.mock.calls.some(([input, init]) => String(input).endsWith("/exports") &&
    init?.method === "POST" && JSON.parse(String(init.body)).animation_id === clip.id)).toBe(true);
});
