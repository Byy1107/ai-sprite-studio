import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DashboardPage } from "./DashboardPage";

afterEach(() => {
  cleanup();
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
  it("shows the Sprint 1 project workspace", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url.endsWith("/projects")) return Promise.resolve(new Response("[]", { status: 200 }));
      return new Promise<Response>(() => undefined);
    });

    renderPage();

    expect(screen.getByRole("heading", { name: "AI Sprite Studio" })).toBeInTheDocument();
    expect(await screen.findByText(/no projects yet/i)).toBeInTheDocument();
    expect(screen.getByText(/AI generation remain disabled/i)).toBeInTheDocument();
  });

  it("shows a healthy backend response", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      if (String(input).endsWith("/projects")) {
        return Promise.resolve(new Response("[]", { status: 200 }));
      }
      return Promise.resolve(new Response(
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
      ));
    });

    renderPage();

    expect(await screen.findByText(/ai-sprite-studio-api 0.1.0 is healthy/i)).toBeInTheDocument();
  });

  it("creates a project from the local workspace form", async () => {
    const project = {
      id: "project-1",
      name: "Sky Knight",
      slug: "sky-knight",
      description: "Local hero",
      root_path: "workspace/sky-knight",
      schema_version: 1,
      created_at: "2026-11-11T00:00:00Z",
      updated_at: "2026-11-11T00:00:00Z",
      last_opened_at: null,
    };
    let projects: typeof project[] = [];
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url = String(input);
      if (url.endsWith("/health")) return new Promise<Response>(() => undefined);
      if (init?.method === "POST") {
        projects = [project];
        return Promise.resolve(new Response(JSON.stringify(project), { status: 201 }));
      }
      return Promise.resolve(new Response(JSON.stringify(projects), { status: 200 }));
    });

    renderPage();
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: /new project/i }));
    await user.type(screen.getByLabelText(/project name/i), "Sky Knight");
    await user.type(screen.getByLabelText(/description/i), "Local hero");
    await user.click(screen.getByRole("button", { name: /create project/i }));

    expect(await screen.findByRole("heading", { name: "Sky Knight" })).toBeInTheDocument();
  });
});
