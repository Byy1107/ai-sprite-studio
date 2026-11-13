import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";

import type { Asset, ExportRecord } from "../../lib/api";
import { ExportPanel } from "./ExportPanel";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const asset: Asset = {
  id: "asset-1", project_id: "project-1", name: "Hero", asset_type: "character",
  style: "eight_bit", width: 16, height: 16, color_mode: "RGBA",
  active_version_id: "version-1", thumbnail_path: "", created_at: "", updated_at: "",
};

it("exports a pinned PNG and a clip sheet without replacing prior records", async () => {
  const user = userEvent.setup();
  const records: ExportRecord[] = [];
  const submitted: Record<string, unknown>[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = input.toString();
    if (url.endsWith("/asset-1/versions")) return new Response(JSON.stringify([
      { id: "version-1", version_number: 1 },
    ]));
    if (url.endsWith("/asset-1/animations")) return new Response(JSON.stringify([
      { id: "clip-1", name: "walk", direction: "down" },
    ]));
    if (url.endsWith("/project-1/exports")) return new Response(JSON.stringify(records));
    if (url.endsWith("/exports") && init?.method === "POST") {
      const payload = JSON.parse(init.body as string) as Record<string, unknown>;
      submitted.push(payload);
      const record: ExportRecord = {
        id: `export-${records.length + 1}`, project_id: "project-1", asset_id: "asset-1",
        format: payload.format as ExportRecord["format"], config: {}, output_path: "",
        checksum: "", status: "succeeded", created_at: "2026-11-13T00:00:00Z",
      };
      records.push(record);
      return new Response(JSON.stringify(record), { status: 201 });
    }
    return new Response("{}", { status: 404 });
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={queryClient}><ExportPanel asset={asset} /></QueryClientProvider>);

  await screen.findByRole("option", { name: "v1" });
  await user.selectOptions(screen.getByLabelText("Export scale"), "4");
  await user.click(screen.getByRole("button", { name: "Export PNG" }));
  await waitFor(() => expect(submitted).toHaveLength(1));
  expect(submitted[0]).toMatchObject({ format: "png", version_id: "version-1", scale: 4 });
  expect(await screen.findByRole("link", { name: "PNG" })).toHaveAttribute(
    "href", "/api/v1/exports/export-1/files/png",
  );
  await user.selectOptions(screen.getByLabelText("Export clip"), "clip-1");
  await user.click(screen.getByRole("button", { name: "Export sheet + JSON" }));
  await waitFor(() => expect(submitted).toHaveLength(2));
  expect(submitted[1]).toMatchObject({
    format: "spritesheet", animation_id: "clip-1", columns: 8, spacing: 0, padding: 0,
  });
  expect(await screen.findByRole("link", { name: "JSON" })).toHaveAttribute(
    "href", "/api/v1/exports/export-2/files/json",
  );
  expect(screen.getAllByRole("link", { name: "PNG" })).toHaveLength(2);
  await user.click(screen.getByRole("button", { name: "Export GIF preview" }));
  await waitFor(() => expect(submitted).toHaveLength(3));
  expect(submitted[2]).toMatchObject({ format: "gif", animation_id: "clip-1" });
  expect(await screen.findByRole("link", { name: "GIF" })).toHaveAttribute(
    "href", "/api/v1/exports/export-3/files/gif",
  );
});
