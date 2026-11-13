import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { GeneratorPanel } from "./GeneratorPanel";

describe("GeneratorPanel", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });
  it("queues a pinned IP-Adapter reference and clears the adapter when disabled", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      if (init?.method === "POST") {
        return Promise.resolve(new Response(JSON.stringify({ id: "job-ip" }), { status: 201 }));
      }
      if (String(input).includes("/system/ai/capabilities")) {
        return Promise.resolve(new Response(JSON.stringify({
          provider: "comfyui", status: "ready", lora_models: [], controlnet_models: [],
          ipadapter_models: ["ip-adapter_sd15.safetensors"],
          clip_vision_models: ["clip-vision.safetensors"],
          detected_nodes: ["IPAdapterAdvanced"], enabled_features: { ipadapter: true },
          message: "IP-Adapter available.",
        })));
      }
      if (String(input).endsWith("/assets")) {
        return Promise.resolve(new Response(JSON.stringify([
          { id: "hero", name: "Hero", active_version_id: "hero-v1", asset_type: "character" },
        ])));
      }
      return Promise.resolve(new Response("[]"));
    });
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={queryClient}><GeneratorPanel projectId="project-1" /></QueryClientProvider>);
    await screen.findByRole("option", { name: "ip-adapter_sd15.safetensors" });
    await userEvent.selectOptions(screen.getByRole("combobox", { name: "Reference asset" }), "hero");
    const adapter = screen.getByRole("combobox", { name: "IP-Adapter model" });
    const vision = screen.getByRole("combobox", { name: "CLIP vision model" });
    expect(vision).toBeDisabled();
    await userEvent.selectOptions(adapter, "ip-adapter_sd15.safetensors");
    await userEvent.selectOptions(vision, "clip-vision.safetensors");
    await userEvent.click(screen.getByRole("button", { name: "Generate character" }));
    const payloads = () => fetchMock.mock.calls.filter((call) => call[1]?.method === "POST")
      .map((call) => JSON.parse(String(call[1]?.body)));
    expect(payloads()[0]).toMatchObject({
      ipadapter_model: "ip-adapter_sd15.safetensors", clip_vision_model: "clip-vision.safetensors",
      reference_asset_id: "hero", reference_version_id: "hero-v1",
    });
    await userEvent.selectOptions(adapter, "");
    expect(vision).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Generate character" }));
    expect(payloads()[1]).toMatchObject({ ipadapter_model: null, clip_vision_model: null });
  });
  it("queues ControlNet with a pinned image and clears its settings when disabled", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      if (init?.method === "POST") {
        return Promise.resolve(new Response(JSON.stringify({ id: "job-control" }), { status: 201 }));
      }
      if (String(input).includes("/system/ai/capabilities")) {
        return Promise.resolve(new Response(JSON.stringify({
          provider: "comfyui", status: "ready", lora_models: [],
          controlnet_models: ["edge.safetensors"], detected_nodes: [],
          enabled_features: { controlnet: true }, message: "ControlNet available.",
        })));
      }
      if (String(input).endsWith("/assets")) {
        return Promise.resolve(new Response(JSON.stringify([
          { id: "edge", name: "Edge map", active_version_id: "edge-v1", asset_type: "item" },
        ])));
      }
      return Promise.resolve(new Response("[]"));
    });
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={queryClient}><GeneratorPanel projectId="project-1" /></QueryClientProvider>);
    await screen.findByRole("option", { name: "edge.safetensors" });
    await userEvent.selectOptions(screen.getByRole("combobox", { name: "Reference asset" }), "edge");
    const picker = screen.getByRole("combobox", { name: "ControlNet model" });
    await userEvent.selectOptions(picker, "edge.safetensors");
    const strength = screen.getByRole("spinbutton", { name: "ControlNet strength" });
    await userEvent.clear(strength);
    await userEvent.type(strength, "0.65");
    await userEvent.click(screen.getByRole("button", { name: "Generate character" }));
    const payloads = () => fetchMock.mock.calls.filter((call) => call[1]?.method === "POST")
      .map((call) => JSON.parse(String(call[1]?.body)));
    expect(payloads()[0]).toMatchObject({
      controlnet_name: "edge.safetensors", controlnet_strength: 0.65,
      controlnet_start: 0, controlnet_end: 1,
      reference_asset_id: "edge", reference_version_id: "edge-v1",
    });
    await userEvent.selectOptions(picker, "");
    expect(strength).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Generate character" }));
    expect(payloads()[1]).toMatchObject({ controlnet_name: null, controlnet_strength: 1 });
    expect(screen.getByText(/No automatic edge, pose or depth extraction/)).toBeInTheDocument();
  });

  it("queues a discovered LoRA and its weight, then disables it explicitly", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      if (init?.method === "POST") {
        return Promise.resolve(new Response(JSON.stringify({ id: "job-lora" }), { status: 201 }));
      }
      if (String(input).includes("/system/ai/capabilities")) {
        return Promise.resolve(new Response(JSON.stringify({
          provider: "comfyui", status: "ready", lora_models: ["pixel.safetensors"],
          detected_nodes: ["LoraLoader"], enabled_features: { lora: true },
          message: "Local LoRA models can be selected.",
        })));
      }
      return Promise.resolve(new Response("[]"));
    });
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={queryClient}><GeneratorPanel projectId="project-1" /></QueryClientProvider>);
    await screen.findByRole("option", { name: "pixel.safetensors" });
    expect(screen.getByText(/Compare the same prompt and seed with No LoRA/)).toBeInTheDocument();
    const picker = screen.getByRole("combobox", { name: "LoRA model" });
    const weight = screen.getByRole("spinbutton", { name: "LoRA weight" });
    expect(weight).toBeDisabled();
    await userEvent.selectOptions(picker, "pixel.safetensors");
    await userEvent.clear(weight);
    await userEvent.type(weight, "0.65");
    await userEvent.click(screen.getByRole("button", { name: "Generate character" }));
    const payloads = () => fetchMock.mock.calls.filter((call) => call[1]?.method === "POST")
      .map((call) => JSON.parse(String(call[1]?.body)));
    expect(payloads()[0]).toMatchObject({ lora_name: "pixel.safetensors", lora_weight: 0.65 });
    await userEvent.selectOptions(picker, "");
    await userEvent.click(screen.getByRole("button", { name: "Generate character" }));
    expect(payloads()[1]).toMatchObject({ lora_name: null, lora_weight: 1 });
  });

  it("pins historical versions across active-version updates, then clears the reference", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      if (init?.method === "POST") {
        return Promise.resolve(new Response(JSON.stringify({ id: "job-1" }), { status: 201 }));
      }
      if (String(input).endsWith("/assets")) {
        return Promise.resolve(new Response(JSON.stringify([
          { id: "hero", name: "Hero reference", active_version_id: "version-1", asset_type: "character" },
          { id: "empty", name: "Empty asset", active_version_id: null },
        ])));
      }
      if (String(input).endsWith("/assets/hero/versions")) {
        return Promise.resolve(new Response(JSON.stringify([
          { id: "version-1", version_number: 2, source: "manual" },
          { id: "version-0", version_number: 1, source: "import" },
        ])));
      }
      return Promise.resolve(new Response("[]"));
    });
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={queryClient}><GeneratorPanel projectId="project-1" /></QueryClientProvider>);
    await screen.findByRole("option", { name: "Hero reference" });
    expect(screen.queryByRole("option", { name: "Empty asset" })).not.toBeInTheDocument();
    const picker = screen.getByRole("combobox", { name: "Reference asset" });
    await userEvent.selectOptions(picker, "hero");
    expect(screen.getByAltText("Reference: Hero reference")).toHaveAttribute("src", "/api/v1/asset-versions/version-1/content");
    const weight = screen.getByRole("spinbutton", { name: "Reference weight (IP-Adapter)" });
    await userEvent.clear(weight);
    await userEvent.type(weight, "0.75");
    await userEvent.click(screen.getByRole("button", { name: "Generate character" }));
    const payloads = () => fetchMock.mock.calls.filter((call) => call[1]?.method === "POST")
      .map((call) => JSON.parse(String(call[1]?.body)));
    expect(payloads()[0]).toMatchObject({ reference_asset_id: "hero", reference_version_id: "version-1", reference_weight: 0.75 });
    await screen.findByRole("option", { name: "Version 1 · import" });
    await userEvent.selectOptions(screen.getByRole("combobox", { name: "Reference version" }), "version-0");
    await act(async () => {
      queryClient.setQueryData(["assets", "project-1"], [
        { id: "hero", name: "Hero reference", active_version_id: "version-2", asset_type: "character" },
      ]);
    });
    expect(screen.getByAltText("Reference: Hero reference")).toHaveAttribute("src", "/api/v1/asset-versions/version-0/content");
    await userEvent.click(screen.getByRole("button", { name: "Generate character" }));
    expect(payloads()[1]).toMatchObject({ reference_asset_id: "hero", reference_version_id: "version-0" });
    await userEvent.selectOptions(picker, "");
    expect(screen.queryByAltText("Reference: Hero reference")).not.toBeInTheDocument();
    expect(weight).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Generate character" }));
    expect(payloads()[2]).toMatchObject({ reference_asset_id: null, reference_version_id: null, reference_weight: 1 });
    expect(screen.getByText(/IP-Adapter uses it for visual guidance/)).toBeInTheDocument();
  });

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
