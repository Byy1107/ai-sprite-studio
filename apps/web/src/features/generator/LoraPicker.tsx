import { useState } from "react";

export function LoraPicker({ models }: { models: string[] }) {
  const [selected, setSelected] = useState("");
  const unavailable = selected !== "" && !models.includes(selected);

  return (
    <fieldset>
      <legend>LoRA style</legend>
      <label>
        LoRA model
        <select name="lora_name" value={selected} onChange={(event) => setSelected(event.target.value)}>
          <option value="">No LoRA</option>
          {unavailable ? <option value={selected}>{selected} (unavailable)</option> : null}
          {models.map((model) => <option key={model} value={model}>{model}</option>)}
        </select>
      </label>
      <label>
        LoRA weight
        <input name="lora_weight" type="number" min="0" max="2" step="0.05" defaultValue="1" required disabled={!selected} />
      </label>
      {unavailable ? (
        <p role="alert">Selected LoRA is no longer listed. Refresh AI capabilities or select No LoRA.</p>
      ) : models.length ? (
        <p>Choose a LoRA compatible with your SD1.5 checkpoint. Weight adjusts both image and text conditioning.</p>
      ) : (
        <p>No LoRA models available. Text generation remains available without LoRA.</p>
      )}
    </fieldset>
  );
}
