import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  importAsset,
  listAssets,
  listAssetVersions,
  restoreAssetVersion,
  type Asset,
} from "../../lib/api";
import { PixelEditor } from "../editor/PixelEditor";
import { AnimationTimeline } from "../animation/AnimationTimeline";

function VersionHistory({ asset }: { asset: Asset }) {
  const queryClient = useQueryClient();
  const versions = useQuery({
    queryKey: ["asset-versions", asset.id],
    queryFn: ({ signal }) => listAssetVersions(asset.id, signal),
  });
  const restore = useMutation({
    mutationFn: (versionId: string) => restoreAssetVersion(asset.id, versionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["asset-versions", asset.id] });
      queryClient.invalidateQueries({ queryKey: ["assets", asset.project_id] });
    },
  });

  return (
    <div className="version-history">
      <h4>Version history</h4>
      {versions.data?.map((version) => (
        <div className="version-row" key={version.id}>
          <span>v{version.version_number} · {version.source}</span>
          <code>{version.checksum.slice(0, 10)}</code>
          {version.id === asset.active_version_id ? (
            <strong>Active</strong>
          ) : (
            <button type="button" onClick={() => restore.mutate(version.id)}>Restore</button>
          )}
        </div>
      ))}
    </div>
  );
}

export function AssetLibrary({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<Asset | null>(null);
  const assets = useQuery({
    queryKey: ["assets", projectId],
    queryFn: ({ signal }) => listAssets(projectId, signal),
  });
  const importer = useMutation({
    mutationFn: (payload: FormData) => importAsset(projectId, payload),
    onSuccess: (asset) => {
      setSelected(asset);
      queryClient.setQueryData<Asset[]>(["assets", projectId], (current = []) => [
        ...current.filter((item) => item.id !== asset.id),
        asset,
      ]);
      queryClient.invalidateQueries({ queryKey: ["assets", projectId] });
    },
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    importer.mutate(new FormData(event.currentTarget));
  }

  return (
    <section className="asset-library" aria-label="Asset library">
      <div className="asset-library__heading">
        <h3>Asset library</h3>
        <span>PNG only · 16 MB maximum</span>
      </div>
      <form className="asset-import" onSubmit={submit}>
        <input aria-label="Asset name" name="name" placeholder="Asset name" required maxLength={120} />
        <select aria-label="Asset type" name="asset_type" defaultValue="character">
          <option value="character">Character</option>
          <option value="item">Item</option>
          <option value="environment">Environment</option>
          <option value="tileset">Tileset</option>
        </select>
        <select aria-label="Asset style" name="style" defaultValue="micro_pixel">
          <option value="micro_pixel">Micro pixel</option>
          <option value="eight_bit">8-bit</option>
          <option value="custom">Custom</option>
        </select>
        <input aria-label="PNG file" name="file" type="file" accept="image/png,.png" required />
        <button type="submit" disabled={importer.isPending}>
          {importer.isPending ? "Importing…" : "Import PNG"}
        </button>
      </form>
      {importer.isError ? <p className="form-error" role="alert">{importer.error.message}</p> : null}
      {assets.data?.length === 0 ? <p className="asset-empty">No assets imported yet.</p> : null}
      <div className="asset-grid">
        {assets.data?.map((asset) => (
          <button className="asset-tile" type="button" key={asset.id} onClick={() => setSelected(asset)}>
            <strong>{asset.name}</strong>
            <span>{asset.asset_type} · {asset.style.replace("_", " ")}</span>
            <span>{asset.width}×{asset.height} · {asset.color_mode}</span>
          </button>
        ))}
      </div>
      {selected ? <PixelEditor asset={selected} /> : null}
      {selected ? <VersionHistory asset={selected} /> : null}
      {selected?.asset_type === "character" ? <AnimationTimeline key={selected.id} asset={selected} /> : null}
    </section>
  );
}
