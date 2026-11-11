import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { PixelEditor } from "./PixelEditor";

afterEach(() => {
  cleanup();
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
});
