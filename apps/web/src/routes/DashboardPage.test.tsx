import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DashboardPage } from "./DashboardPage";

afterEach(() => {
  vi.restoreAllMocks();
});

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <DashboardPage />
    </QueryClientProvider>,
  );
}

describe("DashboardPage", () => {
  it("shows the Sprint 0 scope boundary", () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(
      () => new Promise<Response>(() => undefined),
    );

    renderPage();

    expect(screen.getByRole("heading", { name: "AI Sprite Studio" })).toBeInTheDocument();
    expect(screen.getByText(/generation is not implemented yet/i)).toBeInTheDocument();
  });

  it("shows a healthy backend response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          status: "ok",
          service: "ai-sprite-studio-api",
          version: "0.1.0",
          environment: "test",
          workspace_configured: true,
          database_configured: true,
          comfyui_configured: true,
        }),
        { status: 200 },
      ),
    );

    renderPage();

    expect(await screen.findByText(/ai-sprite-studio-api 0.1.0 is healthy/i)).toBeInTheDocument();
  });
});
