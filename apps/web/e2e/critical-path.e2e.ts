import { expect, test, type Page } from "@playwright/test";

async function spritePng(page: Page): Promise<Buffer> {
  const encoded = await page.evaluate(() => {
    const canvas = document.createElement("canvas");
    canvas.width = 8;
    canvas.height = 8;
    const context = canvas.getContext("2d");
    if (!context) throw new Error("Canvas 2D is unavailable");
    context.fillStyle = "#67b7b2";
    context.fillRect(0, 0, 8, 8);
    return canvas.toDataURL("image/png").split(",")[1];
  });
  return Buffer.from(encoded, "base64");
}

test("project, manual edit, animation, and spritesheet export survive a page reload", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "AI Sprite Studio" })).toBeVisible();

  await page.getByRole("button", { name: "New project" }).click();
  await page.getByLabel("Project name").fill("Browser Smoke Hero");
  await page.getByRole("button", { name: "Create project" }).click();
  await expect(page.getByRole("heading", { name: "Browser Smoke Hero" })).toBeVisible();
  await page.getByRole("button", { name: "Open project" }).click();

  await page.getByLabel("Asset name").fill("Hero");
  await page.getByLabel("PNG file").setInputFiles({
    name: "hero.png", mimeType: "image/png", buffer: await spritePng(page),
  });
  await page.getByRole("button", { name: "Import PNG" }).click();
  await expect(page.getByText("Active version loaded.")).toBeVisible();
  await expect(page.getByRole("region", { name: "Animation timeline" })).toHaveCount(1);

  const canvas = page.getByLabel("Pixel canvas");
  await canvas.focus();
  await canvas.press("ArrowRight");
  await canvas.press("Space");
  await page.getByRole("button", { name: "Publish version" }).click();
  await expect(page.getByText("Manual edit published as a new version.")).toBeVisible();
  await expect(page.getByRole("region", { name: "Animation timeline" })).toHaveCount(1);
  await expect(page.locator(".version-history .version-row").filter({ hasText: "v2 · manual" }).getByText("Active")).toBeVisible();

  await page.getByLabel("Animation name").fill("idle");
  await page.getByRole("button", { name: "Add clip" }).click();
  await expect(page.getByRole("button", { name: "idle · down" })).toBeVisible();
  await page.getByRole("button", { name: "Add frame" }).click();
  await expect(page.locator(".animation-frames").getByText("1 · 125ms")).toBeVisible();
  await page.getByLabel("Export clip").selectOption({ label: "idle · down" });
  await page.getByRole("button", { name: "Export sheet + JSON" }).click();
  const jsonLink = page.getByRole("link", { name: "JSON" });
  await expect(jsonLink).toBeVisible();
  const response = await page.request.get((await jsonLink.getAttribute("href"))!);
  expect(response.ok()).toBe(true);
  const metadata = await response.json();
  expect(metadata.meta.schema_version).toBe(1);
  expect(metadata.animations.idle_down.frames).toHaveLength(1);

  await page.reload();
  await page.getByRole("button", { name: "Open project" }).click();
  await page.getByRole("button", { name: /Hero.*character/ }).click();
  await expect(page.getByText("v2 · manual")).toBeVisible();
  await expect(page.getByRole("button", { name: "idle · down" })).toBeVisible();
  await expect(page.getByRole("link", { name: "JSON" })).toBeVisible();
});

test("renders a 200-asset project from the local API", async ({ page }) => {
  await page.goto("/");
  const created = await page.request.post("/api/v1/projects", { data: { name: "Browser Large Fixture" } });
  expect(created.status()).toBe(201);
  const project = await created.json() as { id: string };
  const png = await spritePng(page);
  for (let index = 0; index < 200; index += 1) {
    const imported = await page.request.post(`/api/v1/projects/${project.id}/assets/import`, {
      multipart: {
        name: `Sprite ${index}`, asset_type: "item", style: "eight_bit",
        file: { name: "sprite.png", mimeType: "image/png", buffer: png },
      },
    });
    expect(imported.status()).toBe(201);
  }
  await page.reload();
  const card = page.locator(".project-card").filter({
    has: page.getByRole("heading", { name: "Browser Large Fixture" }),
  });
  const started = performance.now();
  await card.getByRole("button", { name: "Open project" }).click();
  await expect(card.locator(".asset-tile")).toHaveCount(200, { timeout: 10_000 });
  console.info(`Sprint 10 browser profile: 200 asset tiles rendered in ${(performance.now() - started).toFixed(0)} ms`);
});
