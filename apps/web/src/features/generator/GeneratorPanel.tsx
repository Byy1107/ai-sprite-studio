import { FormEvent, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  assetVersionContentUrl,
  getAICapabilities,
  type Asset,
  cancelGenerationJob,
  acceptGenerationResult,
  createGenerationJob,
  listGenerationResults,
  listGenerationJobs,
  listGenerationPresets,
  type GenerationJob,
  listAssets,
  listAssetVersions,
} from "../../lib/api";

import { LoraPicker } from "./LoraPicker";
import { ControlNetPicker } from "./ControlNetPicker";

const generatorTypes = ["character", "item", "environment", "tileset"] as const;
type GeneratorType = (typeof generatorTypes)[number];

const detailLabels: Record<GeneratorType, string> = {
  character: "Role, outfit, and pose",
  item: "Material and function",
  environment: "Location, mood, and lighting",
  tileset: "Terrain modules and edge rules",
};

function ReferencePicker({ assets }: { assets: Asset[] }) {
  const [assetId, setAssetId] = useState("");
  const [versionId, setVersionId] = useState("");
  const selected = assets.find((asset) => asset.id === assetId && asset.active_version_id);
  const versionsQuery = useQuery({
    queryKey: ["asset-versions", assetId],
    queryFn: ({ signal }) => listAssetVersions(assetId, signal),
    enabled: Boolean(selected),
    retry: false,
  });
  const versions = versionsQuery.data ?? [];
  const selectedVersionListed = versions.some((version) => version.id === versionId);
  return (
    <fieldset>
      <legend>Reference library</legend>
      <p>ControlNet uses the selected version as a prepared control image. Without ControlNet, reference settings are stored only; IP-Adapter is not yet integrated.</p>
      <label>
        Reference asset
        <select name="reference_asset_id" value={selected?.id ?? ""} onChange={(event) => {
          const asset = assets.find((candidate) => candidate.id === event.target.value);
          setAssetId(asset?.id ?? "");
          setVersionId(asset?.active_version_id ?? "");
        }}>
          <option value="">No reference</option>
          {assets.filter((asset) => asset.active_version_id).map((asset) => (
            <option key={asset.id} value={asset.id}>{asset.name}</option>
          ))}
        </select>
      </label>
      <label>
        Reference version
        <select name="reference_version_id" value={selected ? versionId : ""} disabled={!selected}
          onChange={(event) => setVersionId(event.target.value)}>
          {!selected ? <option value="">Choose a reference asset first</option> : null}
          {selected && !selectedVersionListed ? (
            <option value={versionId}>Pinned version ({versionId})</option>
          ) : null}
          {selected ? versions.map((version) => (
            <option key={version.id} value={version.id}>
              Version {version.version_number} · {version.source}
              {version.id === selected.active_version_id ? " (active)" : ""}
            </option>
          )) : null}
        </select>
      </label>
      {selected && versionsQuery.isPending ? <p>Loading reference history…</p> : null}
      {selected && versionsQuery.isError ? (
        <p role="alert">Reference history could not be loaded. The pinned version is preserved.</p>
      ) : null}
      <label>
        Reference weight (reserved for IP-Adapter)
        <input name="reference_weight" type="number" min="0" max="2" step="0.05" defaultValue="1" required disabled={!selected} />
      </label>
      {selected && versionId ? (
        <figure>
          <img src={assetVersionContentUrl(versionId)} alt={`Reference: ${selected.name}`} width="128" height="128" style={{ imageRendering: "pixelated", objectFit: "contain" }} />
          <figcaption>This displayed version is pinned when queued. The original stays unchanged.</figcaption>
        </figure>
      ) : <p>Choose an imported asset from this project as a reference.</p>}
    </fieldset>
  );
}

function JobResults({ job }: { job: GenerationJob }) {
  const queryClient = useQueryClient();
  const resultsQuery = useQuery({
    queryKey: ["generation-results", job.id],
    queryFn: () => listGenerationResults(job.id),
    enabled: job.status === "succeeded",
  });
  const acceptMutation = useMutation({
    mutationFn: acceptGenerationResult,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["generation-results", job.id] });
      queryClient.invalidateQueries({ queryKey: ["assets", job.project_id] });
    },
  });

  return resultsQuery.data?.length ? (
    <div className="job-results">
      {resultsQuery.data.map((result) => (
        <button
          key={result.id}
          type="button"
          disabled={result.selected || !job.asset_id || acceptMutation.isPending}
          onClick={() => acceptMutation.mutate(result.id)}
        >
          {result.selected ? "Accepted" : job.asset_id ? "Accept as version" : "Link an asset to accept"}
        </button>
      ))}
    </div>
  ) : null;
}

export function GeneratorPanel({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient();
  const capabilitiesQuery = useQuery({
    queryKey: ["ai-capabilities"],
    queryFn: ({ signal }) => getAICapabilities(signal),
    retry: false,
    staleTime: 30_000,
  });
  const [assetType, setAssetType] = useState<GeneratorType>("character");
  const [presetId, setPresetId] = useState("");
  const presetsQuery = useQuery({
    queryKey: ["generation-presets"],
    queryFn: ({ signal }) => listGenerationPresets(signal),
  });
  const availablePresets = useMemo(
    () => presetsQuery.data?.filter((preset) => preset.asset_type === assetType) ?? [],
    [assetType, presetsQuery.data],
  );
  const selectedPreset = availablePresets.find((preset) => preset.id === presetId) ?? availablePresets[0];
  const assetsQuery = useQuery({
    queryKey: ["assets", projectId],
    queryFn: ({ signal }) => listAssets(projectId, signal),
  });
  const jobsQuery = useQuery({
    queryKey: ["generation-jobs", projectId],
    queryFn: ({ signal }) => listGenerationJobs(projectId, signal),
    refetchInterval: (query) =>
      query.state.data?.some((job) => ["queued", "running"].includes(job.status)) ? 500 : false,
  });
  const createMutation = useMutation({
    mutationFn: createGenerationJob,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["generation-jobs", projectId] }),
  });
  const cancelMutation = useMutation({
    mutationFn: cancelGenerationJob,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["generation-jobs", projectId] }),
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const detail = String(form.get("detail") ?? "").trim();
    const basePrompt = String(form.get("prompt") ?? "").trim();
    createMutation.mutate({
      project_id: projectId,
      asset_id: String(form.get("asset_id") ?? "") || null,
      prompt: detail ? `${basePrompt}, ${detail}` : basePrompt,
      asset_type: assetType,
      style: String(form.get("style")) as "micro_pixel" | "eight_bit",
      width: Number(form.get("width")),
      height: Number(form.get("height")),
      seed: Number(form.get("seed")),
      preset_id: selectedPreset?.id ?? null,
      negative_prompt: String(form.get("negative_prompt") ?? ""),
      reference_asset_id: String(form.get("reference_asset_id") ?? "") || null,
      reference_version_id: String(form.get("reference_version_id") ?? "") || null,
      reference_weight: Number(form.get("reference_weight") ?? 1),
      lora_name: String(form.get("lora_name") ?? "") || null,
      lora_weight: Number(form.get("lora_weight") ?? 1),
      controlnet_name: String(form.get("controlnet_name") ?? "") || null,
      controlnet_strength: Number(form.get("controlnet_strength") ?? 1),
      controlnet_start: Number(form.get("controlnet_start") ?? 0),
      controlnet_end: Number(form.get("controlnet_end") ?? 1),
    });
  }

  return (
    <section className="generator-panel" aria-labelledby={`generator-${projectId}`}>
      <div className="asset-library__heading">
        <h3 id={`generator-${projectId}`}>Specialized generators</h3>
        <span>Preset-driven · local · provider-neutral</span>
      </div>
      <p className="generator-panel__notice">
        Fake works offline; ComfyUI is used only when explicitly enabled. Presets never download models.
      </p>
      <aside aria-label="Optional AI capabilities">
        <p>{capabilitiesQuery.isError
          ? "Capability check unavailable. Optional AI features remain disabled."
          : capabilitiesQuery.data?.message ?? "Checking optional AI features…"}</p>
        {capabilitiesQuery.data?.detected_nodes?.length ? (
          <p>Detected nodes: {capabilitiesQuery.data.detected_nodes.join(", ")}. Models and workflows are not verified.</p>
        ) : null}
        <button type="button" disabled={capabilitiesQuery.isFetching} onClick={() => void capabilitiesQuery.refetch()}>
          Refresh AI capabilities
        </button>
      </aside>
      <div className="generator-types" role="group" aria-label="Generator type">
        {generatorTypes.map((type) => (
          <button
            key={type}
            type="button"
            aria-pressed={assetType === type}
            onClick={() => {
              setAssetType(type);
              setPresetId("");
            }}
          >
            {type[0].toUpperCase() + type.slice(1)}
          </button>
        ))}
      </div>
      <form className="generator-form" key={`${projectId}:${assetType}:${selectedPreset?.id}`} onSubmit={submit}>
        <label>
          Preset
          <select value={selectedPreset?.id ?? ""} onChange={(event) => setPresetId(event.target.value)}>
            {availablePresets.map((preset) => (
              <option key={preset.id} value={preset.id}>{preset.label}</option>
            ))}
          </select>
        </label>
        {selectedPreset ? <p className="generator-panel__notice">{selectedPreset.description}</p> : null}
        <label>
          Base prompt
          <textarea name="prompt" required maxLength={1000} defaultValue={selectedPreset?.prompt ?? "pixel art game asset"} />
        </label>
        <label>
          {detailLabels[assetType]}
          <input name="detail" maxLength={300} placeholder="Optional creative direction" />
        </label>
        <label>
          Avoid
          <textarea name="negative_prompt" maxLength={1000} defaultValue={selectedPreset?.negative_prompt ?? "blur, anti-aliasing"} />
        </label>
        <label>
          Target asset
          <select name="asset_id" defaultValue="">
            <option value="">Candidate only</option>
            {assetsQuery.data?.filter((asset) => asset.asset_type === assetType).map((asset) => (
              <option key={asset.id} value={asset.id}>{asset.name} ({asset.width}×{asset.height})</option>
            ))}
          </select>
        </label>
        <label>
          Style
          <select name="style" defaultValue={selectedPreset?.style ?? "eight_bit"}>
            <option value="micro_pixel">Micro pixel</option>
            <option value="eight_bit">8-bit</option>
          </select>
        </label>
        <label>Width<input name="width" type="number" min="8" max="256" defaultValue={selectedPreset?.width ?? 32} /></label>
        <label>Height<input name="height" type="number" min="8" max="256" defaultValue={selectedPreset?.height ?? 32} /></label>
        <label>Seed<input name="seed" type="number" min="0" defaultValue="1" /></label>
        {assetsQuery.isError ? <p role="alert">Reference library unavailable: {assetsQuery.error.message}</p> : null}
        <ReferencePicker assets={assetsQuery.data ?? []} />
        <LoraPicker models={capabilitiesQuery.isError ? [] : capabilitiesQuery.data?.lora_models ?? []} />
        <ControlNetPicker models={capabilitiesQuery.isError ? [] : capabilitiesQuery.data?.controlnet_models ?? []} />
        <button type="submit" disabled={createMutation.isPending}>
          {createMutation.isPending ? "Queueing…" : `Generate ${assetType}`}
        </button>
      </form>
      {createMutation.isError || jobsQuery.isError ? (
        <p className="form-error" role="alert">
          {(createMutation.error ?? jobsQuery.error)?.message}
        </p>
      ) : null}
      <div className="job-list">
        {jobsQuery.data?.map((job) => (
          <article className="job-row" key={job.id}>
            <div>
              <strong>{String(job.request.prompt)}</strong>
              <span>{job.provider} · {job.status} · {Math.round(job.progress * 100)}%</span>
            </div>
            {["queued", "running"].includes(job.status) ? (
              <button type="button" onClick={() => cancelMutation.mutate(job.id)}>Cancel</button>
            ) : null}
            {job.error_message ? <p className="form-error">{job.error_message}</p> : null}
            <JobResults job={job} />
          </article>
        ))}
      </div>
    </section>
  );
}
