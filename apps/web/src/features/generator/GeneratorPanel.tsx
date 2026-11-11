import { FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  cancelGenerationJob,
  createGenerationJob,
  listGenerationJobs,
} from "../../lib/api";

export function GeneratorPanel({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient();
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
    createMutation.mutate({
      project_id: projectId,
      prompt: String(form.get("prompt") ?? ""),
      asset_type: String(form.get("asset_type")) as "character",
      style: String(form.get("style")) as "eight_bit",
      width: Number(form.get("width")),
      height: Number(form.get("height")),
      seed: Number(form.get("seed")),
    });
  }

  return (
    <section className="generator-panel" aria-labelledby={`generator-${projectId}`}>
      <div className="asset-library__heading">
        <h3 id={`generator-${projectId}`}>Fake generator</h3>
        <span>Deterministic · local · no GPU</span>
      </div>
      <p className="generator-panel__notice">
        Development preview only. ComfyUI and real model generation are not connected.
      </p>
      <form className="generator-form" onSubmit={submit}>
        <label>
          Prompt
          <textarea name="prompt" required maxLength={1000} defaultValue="dark fantasy sky guardian" />
        </label>
        <label>
          Asset type
          <select name="asset_type" defaultValue="character">
            <option value="character">Character</option>
            <option value="item">Item</option>
            <option value="environment">Environment</option>
            <option value="tileset">Tileset</option>
          </select>
        </label>
        <label>
          Style
          <select name="style" defaultValue="eight_bit">
            <option value="micro_pixel">Micro pixel</option>
            <option value="eight_bit">8-bit</option>
          </select>
        </label>
        <label>Width<input name="width" type="number" min="8" max="256" defaultValue="32" /></label>
        <label>Height<input name="height" type="number" min="8" max="256" defaultValue="32" /></label>
        <label>Seed<input name="seed" type="number" min="0" defaultValue="1" /></label>
        <button type="submit" disabled={createMutation.isPending}>
          {createMutation.isPending ? "Queueing…" : "Run fake generation"}
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
          </article>
        ))}
      </div>
    </section>
  );
}
