import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { GeneratorPanel } from "./GeneratorPanel";

describe("GeneratorPanel", () => {
  it("queues a preset-driven character generation job", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      if (init?.method === "POST") {
        return Promise.resolve(new Response(JSON.stringify({ id: "job-1", status: "queued" }), { status: 201 }));
      }
      if (String(input).includes("generation-presets")) {
        return Promise.resolve(new Response(JSON.stringify([{
          id: "character-hero",
          label: "Hero",
          asset_type: "character",
          description: "Readable hero",
          prompt: "centered hero",
          negative_prompt: "blur",
          style: "eight_bit",
          width: 48,
          height: 48,
          version: "1.0",
        }]), { status: 200 }));
      }
      return Promise.resolve(new Response("[]", { status: 200 }));
    });
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <GeneratorPanel projectId="project-1" />
      </QueryClientProvider>,
    );

    await screen.findByText("Readable hero");
    await userEvent.click(screen.getByRole("button", { name: /generate character/i }));
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/generation-jobs"),
      expect.objectContaining({ method: "POST" }),
    );
    expect(screen.getByRole("button", { name: "Tileset" })).toBeInTheDocument();
    expect(screen.getByText(/presets never download models/i)).toBeInTheDocument();
  });
});
