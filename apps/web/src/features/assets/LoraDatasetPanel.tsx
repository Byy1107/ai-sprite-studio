import { FormEvent, useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { downloadLoraDataset, type Asset } from "../../lib/api";

export function LoraDatasetPanel({ projectId, assets }: { projectId: string; assets: Asset[] }) {
  const [selectionError, setSelectionError] = useState("");
  const download = useMutation({
    mutationFn: (payload: Parameters<typeof downloadLoraDataset>[1]) =>
      downloadLoraDataset(projectId, payload),
    onSuccess: (archive) => {
      const url = URL.createObjectURL(archive);
      const link = document.createElement("a");
      link.href = url;
      link.download = "lora-dataset.zip";
      document.body.append(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    },
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const fields = new FormData(event.currentTarget);
    const samples = assets.filter((asset) => asset.active_version_id && fields.has(`include-${asset.id}`))
      .map((asset) => ({
        version_id: asset.active_version_id!,
        caption: String(fields.get(`caption-${asset.id}`) ?? "").trim(),
      }));
    if (samples.length === 0) {
      setSelectionError("Select at least one published asset.");
      return;
    }
    setSelectionError("");
    download.mutate({
      samples,
      resolution: Number(fields.get("resolution")) as 256 | 512,
      background: String(fields.get("background") ?? "#FFFFFF").slice(1),
    });
  }

  return (
    <section className="export-panel" aria-label="LoRA dataset preparation">
      <h4>Prepare LoRA training data</h4>
      <p>Select only artwork you have rights to train on. This exports a local ZIP of pinned, captioned versions; it does not train or upload a model.</p>
      <form onSubmit={submit}>
        {assets.filter((asset) => asset.active_version_id).map((asset) => (
          <div className="animation-row" key={asset.id}>
            <label><input type="checkbox" name={`include-${asset.id}`} /> {asset.name}</label>
            <label>Caption for {asset.name}<input name={`caption-${asset.id}`} maxLength={240}
              defaultValue={`${asset.name}, ${asset.style.replace("_", " ")} pixel art`} /></label>
          </div>
        ))}
        <div className="animation-row">
          <label>Training image size <select name="resolution" defaultValue="512">
            <option value="256">256×256</option><option value="512">512×512</option>
          </select></label>
          <label>Transparency background <input name="background" type="color" defaultValue="#ffffff" /></label>
          <button type="submit" disabled={download.isPending || assets.length === 0}>
            {download.isPending ? "Preparing…" : "Download LoRA dataset"}
          </button>
        </div>
      </form>
      {selectionError && <p className="form-error" role="alert">{selectionError}</p>}
      {download.isError && <p className="form-error" role="alert">{download.error.message}</p>}
    </section>
  );
}
