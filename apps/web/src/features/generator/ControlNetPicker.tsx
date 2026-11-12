import { useState } from "react";

export function ControlNetPicker({ models }: { models: string[] }) {
  const [selected, setSelected] = useState("");
  const [start, setStart] = useState(0);
  const unavailable = selected !== "" && !models.includes(selected);

  return (
    <fieldset>
      <legend>ControlNet guidance</legend>
      <label>
        ControlNet model
        <select name="controlnet_name" value={selected} onChange={(event) => setSelected(event.target.value)}>
          <option value="">No ControlNet</option>
          {unavailable ? <option value={selected}>{selected} (unavailable)</option> : null}
          {models.map((model) => <option key={model} value={model}>{model}</option>)}
        </select>
      </label>
      <label>
        ControlNet strength
        <input name="controlnet_strength" type="number" min="0" max="2" step="0.05" defaultValue="1" required disabled={!selected} />
      </label>
      <label>
        ControlNet start
        <input name="controlnet_start" type="number" min="0" max="0.99" step="0.01" value={start}
          onChange={(event) => setStart(Number(event.target.value))} required disabled={!selected} />
      </label>
      <label>
        ControlNet end
        <input name="controlnet_end" type="number" min={Number((start + 0.01).toFixed(2))} max="1" step="0.01" defaultValue="1" required disabled={!selected} />
      </label>
      {unavailable ? <p role="alert">Selected ControlNet is no longer listed. Refresh models or select No ControlNet.</p> : null}
      <p>Choose a reference asset and version above as the prepared control image, such as an edge map for a matching SD1.5 ControlNet. No automatic edge, pose or depth extraction is applied.</p>
    </fieldset>
  );
}
