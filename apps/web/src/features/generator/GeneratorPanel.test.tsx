import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { GeneratorPanel } from "./GeneratorPanel";

describe("GeneratorPanel", () => {
  it("queues a deterministic fake generation job", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((_input, init) => {
      if (init?.method === "POST") {
        return Promise.resolve(new Response(JSON.stringify({ id: "job-1", status: "queued" }), { status: 201 }));
      }
      return Promise.resolve(new Response("[]", { status: 200 }));
    });
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <GeneratorPanel projectId="project-1" />
      </QueryClientProvider>,
    );

    await userEvent.click(await screen.findByRole("button", { name: /run fake generation/i }));
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/generation-jobs"),
      expect.objectContaining({ method: "POST" }),
    );
    expect(screen.getByText(/comfyui and real model generation are not connected/i)).toBeInTheDocument();
  });
});
