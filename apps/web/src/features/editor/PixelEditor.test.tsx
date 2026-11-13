import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { PixelEditor } from "./PixelEditor";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  Reflect.deleteProperty(Image.prototype, "decode");
});

describe("PixelEditor", () => {
  it("exposes core tools and grid control", async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <PixelEditor asset={{
          id: "asset-1",
          project_id: "project-1",
          name: "Knight",
          asset_type: "character",
          style: "eight_bit",
          width: 16,
          height: 24,
          color_mode: "RGBA",
          active_version_id: null,
          thumbnail_path: "preview.png",
          created_at: "2026-11-11T00:00:00Z",
          updated_at: "2026-11-11T00:00:00Z",
        }} />
      </QueryClientProvider>,
    );

    expect(screen.getByRole("button", { name: "Pencil" })).toHaveAttribute("aria-pressed", "true");
    await userEvent.click(screen.getByRole("button", { name: "Rectangle" }));
    expect(screen.getByRole("button", { name: "Rectangle" })).toHaveAttribute("aria-pressed", "true");
    const grid = screen.getByRole("checkbox", { name: "Grid" });
    expect(grid).toBeChecked();
    await userEvent.click(grid);
    expect(grid).not.toBeChecked();
  });

  it("queues variation and selected-region inpaint against a published version", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      if (init?.method === "POST") {
        return Promise.resolve(new Response(JSON.stringify({ id: "edit-job" }), { status: 201 }));
      }
      if (String(input).includes("/system/ai/capabilities")) {
        return Promise.resolve(new Response(JSON.stringify({
          provider: "comfyui", status: "ready",
          enabled_features: { variation: true, inpaint: true }, message: "Edit available.",
        })));
      }
      if (String(input).endsWith("/versions")) {
        return Promise.resolve(new Response(JSON.stringify([{ id: "version-1", version_number: 1 }])));
      }
      return Promise.resolve(new Response("[]"));
    });
    Object.defineProperty(Image.prototype, "decode", {
      configurable: true, value: vi.fn().mockResolvedValue(undefined),
    });
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({
      drawImage: vi.fn(), clearRect: vi.fn(), putImageData: vi.fn(),
      getImageData: () => ({ width: 16, height: 16, data: new Uint8ClampedArray(16 * 16 * 4) }),
    } as unknown as CanvasRenderingContext2D);
    vi.stubGlobal("ImageData", class {
      constructor(public data: Uint8ClampedArray, public width: number, public height: number) {}
    });
    vi.stubGlobal("localStorage", {
      getItem: () => null, setItem: vi.fn(), removeItem: vi.fn(),
    });
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={queryClient}><PixelEditor asset={{
      id: "asset-1", project_id: "project-1", name: "Knight", asset_type: "character",
      style: "eight_bit", width: 16, height: 16, color_mode: "RGBA",
      active_version_id: "version-1", thumbnail_path: "preview.png",
      created_at: "2026-11-11T00:00:00Z", updated_at: "2026-11-11T00:00:00Z",
    }} /></QueryClientProvider>);
    const variation = await screen.findByRole("button", { name: "Generate variation" });
    await waitFor(() => expect(variation).toBeEnabled());
    await userEvent.click(variation);
    const canvas = screen.getByLabelText("Pixel canvas");
    vi.spyOn(canvas, "getBoundingClientRect").mockReturnValue({
      left: 0, top: 0, width: 160, height: 160, right: 160, bottom: 160,
      x: 0, y: 0, toJSON: () => ({}),
    });
    await userEvent.click(screen.getByRole("button", { name: "Select region" }));
    fireEvent(canvas, new MouseEvent("pointerdown", { bubbles: true, clientX: 10, clientY: 20 }));
    fireEvent(canvas, new MouseEvent("pointermove", { bubbles: true, clientX: 39, clientY: 49 }));
    fireEvent(canvas, new MouseEvent("pointerup", { bubbles: true, clientX: 39, clientY: 49 }));
    await userEvent.click(screen.getByRole("button", { name: "Inpaint selection" }));
    const payloads = fetchMock.mock.calls.filter((call) => call[1]?.method === "POST")
      .map((call) => JSON.parse(String(call[1]?.body)));
    expect(payloads[0]).toMatchObject({
      operation: "variation", reference_asset_id: "asset-1", reference_version_id: "version-1",
    });
    expect(payloads[1]).toMatchObject({
      operation: "inpaint", mask_x: 1, mask_y: 2, mask_width: 3, mask_height: 3,
      reference_asset_id: "asset-1", reference_version_id: "version-1",
    });
  });
});
