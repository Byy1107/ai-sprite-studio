import { useState } from "react";

export function IPAdapterPicker({ models, visionModels }: {
  models: string[]; visionModels: string[];
}) {
  const available = models.length > 0 && visionModels.length > 0;
  const [selected, setSelected] = useState("");
  return (
    <fieldset>
      <legend>IP-Adapter reference guidance</legend>
      <p>Uses the pinned reference image and its weight. Requires a compatible local SD1.5 adapter and CLIP vision model.</p>
      <label>IP-Adapter model
        <select name="ipadapter_model" disabled={!available} value={selected} onChange={(event) => setSelected(event.target.value)}>
          <option value="">No IP-Adapter</option>
          {models.map((model) => <option key={model} value={model}>{model}</option>)}
        </select>
      </label>
      <label>CLIP vision model
        <select name="clip_vision_model" disabled={!available || !selected} required={Boolean(selected)} defaultValue="">
          <option value="">Choose CLIP vision</option>
          {visionModels.map((model) => <option key={model} value={model}>{model}</option>)}
        </select>
      </label>
      {!available && <p>No compatible IP-Adapter loader and local model catalogue detected.</p>}
    </fieldset>
  );
}
