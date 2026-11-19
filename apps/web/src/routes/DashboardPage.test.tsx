import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
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
    expect(screen.getByText(/enable comfyui explicitly/i)).toBeInTheDocument();
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

  it("reports missing project files without modifying them", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url.endsWith("/projects")) return Promise.resolve(new Response(JSON.stringify([{
        id: "project-1", name: "Sky Knight", slug: "sky-knight", description: "",
        root_path: "workspace/sky-knight", schema_version: 1,
        created_at: "2026-11-11T00:00:00Z", updated_at: "2026-11-11T00:00:00Z",
        last_opened_at: null,
      }])));
      if (url.endsWith("/integrity")) return Promise.resolve(new Response(JSON.stringify({
        project_id: "project-1", status: "issues",
        issues: [{ kind: "missing_asset_version", reference_id: "version-1", path: "assets/hero.png" }],
      })));
      return new Promise<Response>(() => undefined);
    });
    renderPage();
    await userEvent.click(await screen.findByRole("button", { name: "Check files" }));
    expect(await screen.findByText(/missing_asset_version: assets\/hero.png/)).toBeInTheDocument();
    expect(screen.getByText(/No files were changed/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Download backup" })).toHaveAttribute(
      "href", expect.stringContaining("/projects/project-1/backup"),
    );
  });

  it("restores an uploaded local project backup", async () => {
    const project = {
      id: "restored-1", name: "Restored Hero", slug: "restored-hero", description: "",
      root_path: "workspace/restored-hero", schema_version: 1,
      created_at: "2026-11-11T00:00:00Z", updated_at: "2026-11-11T00:00:00Z",
      last_opened_at: null,
    };
    let projects: typeof project[] = [];
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      if (String(input).endsWith("/projects/restore") && init?.method === "POST") {
        projects = [project];
        return Promise.resolve(new Response(JSON.stringify(project), { status: 201 }));
      }
      if (String(input).endsWith("/projects")) {
        return Promise.resolve(new Response(JSON.stringify(projects)));
      }
      return new Promise<Response>(() => undefined);
    });
    renderPage();
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Restore backup" }));
    await user.upload(screen.getByLabelText("Backup ZIP"), new File(["zip"], "project.zip", {
      type: "application/zip",
    }));
    await user.click(screen.getByRole("button", { name: "Restore project" }));
    await waitFor(() => expect(fetchMock.mock.calls.map((call) => [String(call[0]), call[1]?.method, call[1]?.body?.constructor.name])).toContainEqual(["/api/v1/projects/restore", "POST", "FormData"]));
    expect(await screen.findByRole("heading", { name: "Restored Hero" })).toBeInTheDocument();
  });

  it("clears cache only after confirmation", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      if (String(input).endsWith("/projects")) return Promise.resolve(new Response(JSON.stringify([{
        id: "project-1", name: "Sky Knight", slug: "sky-knight", description: "",
        root_path: "workspace/sky-knight", schema_version: 1,
        created_at: "2026-11-11T00:00:00Z", updated_at: "2026-11-11T00:00:00Z",
        last_opened_at: null,
      }])));
      if (String(input).endsWith("/cache") && init?.method === "DELETE") {
        return Promise.resolve(new Response(JSON.stringify({ removed_files: 2 })));
      }
      return new Promise<Response>(() => undefined);
    });
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    renderPage();
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Clear cache" }));
    expect(fetchMock.mock.calls.some((call) => call[1]?.method === "DELETE")).toBe(false);
    confirm.mockReturnValue(true);
    await user.click(screen.getByRole("button", { name: "Clear cache" }));
    expect(await screen.findByText("Removed 2 cache files.")).toBeInTheDocument();
  });
});
