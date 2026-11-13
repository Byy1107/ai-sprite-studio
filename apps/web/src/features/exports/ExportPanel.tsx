import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createExport, exportFileUrl, listAnimations, listAssetVersions, listExports,
  type Asset,
} from "../../lib/api";

export function ExportPanel({ asset }: { asset: Asset }) {
  const queryClient = useQueryClient();
  const [scale, setScale] = useState<1 | 2 | 4 | 8>(1);
  const [versionId, setVersionId] = useState("");
  const [animationId, setAnimationId] = useState("");
  const versions = useQuery({
    queryKey: ["asset-versions", asset.id],
    queryFn: ({ signal }) => listAssetVersions(asset.id, signal),
  });
  const clips = useQuery({
    queryKey: ["animations", asset.id],
    queryFn: ({ signal }) => listAnimations(asset.id, signal),
    enabled: asset.asset_type === "character",
  });
  const exportsQuery = useQuery({
    queryKey: ["exports", asset.project_id],
    queryFn: ({ signal }) => listExports(asset.project_id, signal),
  });
  const mutation = useMutation({
    mutationFn: createExport,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["exports", asset.project_id] }),
  });
  const assetExports = exportsQuery.data?.filter((record) => record.asset_id === asset.id) ?? [];
  const selectedVersion = versionId || versions.data?.[0]?.id || asset.active_version_id || "";

  function exportPng() {
    if (!selectedVersion) return;
    mutation.mutate({ asset_id: asset.id, format: "png", version_id: selectedVersion, scale });
  }

  function exportSheet(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!animationId) return;
    const data = new FormData(event.currentTarget);
    mutation.mutate({
      asset_id: asset.id, format: "spritesheet", animation_id: animationId, scale,
      columns: Number(data.get("columns")), spacing: Number(data.get("spacing")),
      padding: Number(data.get("padding")),
    });
  }

  return (
    <section className="export-panel" aria-label="Export asset">
      <h4>Export · {asset.name}</h4>
      <p>Each export creates new files; previous exports are never overwritten.</p>
      <label>Scale <select aria-label="Export scale" value={scale}
        onChange={(event) => setScale(Number(event.target.value) as 1 | 2 | 4 | 8)}>
        <option value={1}>1×</option><option value={2}>2×</option>
        <option value={4}>4×</option><option value={8}>8×</option>
      </select></label>
      <div className="animation-row">
        <label>Version <select aria-label="Export version" value={selectedVersion}
          onChange={(event) => setVersionId(event.target.value)}>
          {versions.data?.map((version) => <option key={version.id} value={version.id}>
            v{version.version_number}
          </option>)}
        </select></label>
        <button type="button" disabled={mutation.isPending || !selectedVersion}
          onClick={exportPng}>Export PNG</button>
      </div>
      {asset.asset_type === "character" && <form className="animation-row" onSubmit={exportSheet}>
        <label>Clip <select aria-label="Export clip" value={animationId}
          onChange={(event) => setAnimationId(event.target.value)}>
          <option value="">Select clip</option>
          {clips.data?.map((clip) => <option key={clip.id} value={clip.id}>{clip.name} · {clip.direction}</option>)}
        </select></label>
        <label>Columns <input aria-label="Sheet columns" name="columns" type="number" min="1" max="64" defaultValue="8" required /></label>
        <label>Spacing <input aria-label="Sheet spacing" name="spacing" type="number" min="0" max="64" defaultValue="0" required /></label>
        <label>Padding <input aria-label="Sheet padding" name="padding" type="number" min="0" max="64" defaultValue="0" required /></label>
        <button type="submit" disabled={mutation.isPending || !animationId}>Export sheet + JSON</button>
        <button type="button" disabled={mutation.isPending || !animationId}
          onClick={() => mutation.mutate({ asset_id: asset.id, format: "gif", animation_id: animationId, scale })}>
          Export GIF preview
        </button>
      </form>}
      {mutation.isError && <p className="form-error" role="alert">{mutation.error.message}</p>}
      {exportsQuery.isError && <p className="form-error" role="alert">Could not load exports.</p>}
      {assetExports.map((record) => <div className="version-row" key={record.id}>
        <span>{record.format} · {new Date(record.created_at).toLocaleString()}</span>
        {record.format === "gif"
          ? <a href={exportFileUrl(record.id, "gif")} download>GIF</a>
          : <a href={exportFileUrl(record.id, "png")} download>PNG</a>}
        {record.format === "spritesheet" && <a href={exportFileUrl(record.id, "json")} download>JSON</a>}
      </div>)}
    </section>
  );
}
