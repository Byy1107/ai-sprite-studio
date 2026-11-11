import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AssetLibrary } from "./AssetLibrary";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

function renderLibrary() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <AssetLibrary projectId="project-1" />
    </QueryClientProvider>,
  );
}

describe("AssetLibrary", () => {
  it("imports a PNG and shows its metadata", async () => {
    const asset = {
      id: "asset-1",
      project_id: "project-1",
      name: "Sky Knight",
      asset_type: "character",
      style: "eight_bit",
      width: 16,
      height: 24,
      color_mode: "RGBA",
      active_version_id: "version-1",
      thumbnail_path: "assets/asset-1/thumbnails/preview.png",
      created_at: "2026-11-11T00:00:00Z",
      updated_at: "2026-11-11T00:00:00Z",
    };
    let assets: typeof asset[] = [];
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url = input.toString();
      if (init?.method === "POST") {
        assets = [asset];
        return Promise.resolve(new Response(JSON.stringify(asset), { status: 201 }));
      }
      if (url.includes("/versions")) {
        return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify(assets), { status: 200 }));
    });

    renderLibrary();
    await screen.findByText("No assets imported yet.");
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Asset name"), "Sky Knight");
    await user.selectOptions(screen.getByLabelText("Asset style"), "eight_bit");
    await user.upload(
      screen.getByLabelText("PNG file"),
      new File(["png"], "hero.png", { type: "image/png" }),
    );
    fireEvent.submit(screen.getByRole("button", { name: "Import PNG" }).closest("form")!);

    expect(await screen.findByRole("button", { name: /Sky Knight/i })).toHaveTextContent("16×24");
  });
});
