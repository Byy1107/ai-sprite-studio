import { existsSync, mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "@playwright/test";

const webDir = fileURLToPath(new URL(".", import.meta.url));
const apiDir = resolve(webDir, "../api");
const scratch = mkdtempSync(join(tmpdir(), "ai-sprite-e2e-"));
const python = [
  process.env.AI_SPRITE_PYTHON,
  join(apiDir, ".venv-local", "Scripts", "python.exe"),
  join(apiDir, ".venv", "Scripts", "python.exe"),
].find((candidate) => candidate && existsSync(candidate)) ?? "python";

export default defineConfig({
  testDir: "./e2e",
  testMatch: "*.e2e.ts",
  workers: 1,
  retries: 0,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:5173",
    browserName: "chromium",
    channel: "chrome",
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command: `"${python}" -m uvicorn app.main:app --host 127.0.0.1 --port 8000`,
      cwd: apiDir,
      env: {
        ...process.env,
        AI_SPRITE_WORKSPACE_DIR: join(scratch, "workspace"),
        AI_SPRITE_DATABASE_URL: `sqlite:///${join(scratch, "studio.db").replace(/\\/g, "/")}`,
        AI_SPRITE_AI_PROVIDER: "fake",
      },
      url: "http://127.0.0.1:8000/api/v1/health",
      reuseExistingServer: false,
    },
    {
      command: `"${process.execPath}" "${join(webDir, "node_modules", "vite", "bin", "vite.js")}" --host 127.0.0.1 --port 5173 --strictPort`,
      cwd: webDir,
      url: "http://127.0.0.1:5173",
      reuseExistingServer: false,
    },
  ],
});
