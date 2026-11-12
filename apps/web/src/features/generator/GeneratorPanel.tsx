import { FormEvent, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  cancelGenerationJob,
  acceptGenerationResult,
  createGenerationJob,
  listGenerationResults,
  listGenerationJobs,
  listGenerationPresets,
  type GenerationJob,
  listAssets,
} from "../../lib/api";

const generatorTypes = ["character", "item", "environment", "tileset"] as const;
type GeneratorType = (typeof generatorTypes)[number];

const detailLabels: Record<GeneratorType, string> = {
  character: "Role, outfit, and pose",
  item: "Material and function",
  environment: "Location, mood, and lighting",
  tileset: "Terrain modules and edge rules",
};

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
      <form className="generator-form" key={`${assetType}:${selectedPreset?.id}`} onSubmit={submit}>
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
