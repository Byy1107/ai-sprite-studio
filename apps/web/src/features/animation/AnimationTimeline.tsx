import { FormEvent, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  addAnimationFrame, assetVersionContentUrl, createAnimation, deleteAnimation,
  deleteAnimationFrame, duplicateAnimationFrame, listAnimationFrames, listAnimations,
  listAssetVersions, reorderAnimationFrames, updateAnimation, updateAnimationFrame,
  type AnimationClip, type AnimationFrame, type Asset,
} from "../../lib/api";
import { frameAtTime } from "./timing";

export function AnimationTimeline({ asset }: { asset: Asset }) {
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedFrameId, setSelectedFrameId] = useState<string | null>(null);
  const [playing, setPlaying] = useState(false);
  const [elapsedMs, setElapsedMs] = useState(0);
  const [onionSkin, setOnionSkin] = useState(false);
  const [draggedId, setDraggedId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const clips = useQuery({ queryKey: ["animations", asset.id], queryFn: ({ signal }) => listAnimations(asset.id, signal) });
  const versions = useQuery({ queryKey: ["asset-versions", asset.id], queryFn: ({ signal }) => listAssetVersions(asset.id, signal) });
  const selectedClip = clips.data?.find((clip) => clip.id === selectedId) ?? null;
  const frames = useQuery({
    queryKey: ["animation-frames", selectedId],
    queryFn: ({ signal }) => listAnimationFrames(selectedId!, signal),
    enabled: Boolean(selectedId),
  });
  const orderedFrames = useMemo(() => frames.data ?? [], [frames.data]);
  const previewIndex = playing && selectedClip ? frameAtTime(orderedFrames, selectedClip.loop_mode, elapsedMs)
    : Math.max(0, orderedFrames.findIndex((frame) => frame.id === selectedFrameId));
  const currentFrame = orderedFrames[previewIndex];
  const previousFrame = orderedFrames[previewIndex - 1];
  const nextFrame = orderedFrames[previewIndex + 1];

  useEffect(() => {
    if (!playing || !selectedClip || orderedFrames.length === 0) return;
    let start: number | undefined;
    let handle = 0;
    const total = orderedFrames.reduce((sum, frame) => sum + frame.duration_ms, 0);
    const tick = (now: number) => {
      start ??= now;
      const elapsed = now - start;
      setElapsedMs(elapsed);
      if (selectedClip.loop_mode === "once" && elapsed >= total) {
        setSelectedFrameId(orderedFrames[orderedFrames.length - 1].id);
        setPlaying(false);
        return;
      }
      handle = requestAnimationFrame(tick);
    };
    handle = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(handle);
  }, [playing, selectedClip, orderedFrames]);

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["animations", asset.id] });
    queryClient.invalidateQueries({ queryKey: ["animation-frames", selectedId] });
  };
  const run = async (action: () => Promise<unknown>) => {
    setError(null);
    try {
      await action();
      refresh();
    } catch (problem) {
      setError(problem instanceof Error ? problem.message : "Animation update failed.");
    }
  };
  const create = useMutation({
    mutationFn: (name: string) => createAnimation(asset.id, { name, direction: "down", fps: 8, loop_mode: "loop" }),
    onSuccess: (clip) => { setSelectedId(clip.id); refresh(); },
  });

  function createClip(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const name = new FormData(form).get("name")?.toString().trim();
    if (name) create.mutate(name, { onSuccess: () => form.reset() });
  }

  function selectClip(clip: AnimationClip) {
    setSelectedId(clip.id);
    setSelectedFrameId(null);
    setPlaying(false);
    setElapsedMs(0);
  }

  function changeFrame(frame: AnimationFrame, change: Partial<AnimationFrame>) {
    void run(() => updateAnimationFrame(frame.id, change));
  }

  function moveFrame(sourceId: string, targetId: string) {
    if (!selectedClip || sourceId === targetId) return;
    const ids = orderedFrames.map((frame) => frame.id);
    const sourceIndex = ids.indexOf(sourceId);
    const targetIndex = ids.indexOf(targetId);
    if (sourceIndex < 0 || targetIndex < 0) return;
    ids.splice(sourceIndex, 1);
    ids.splice(targetIndex, 0, sourceId);
    void run(() => reorderAnimationFrames(selectedClip.id, ids));
  }

  if (asset.asset_type !== "character") return null;

  return (
    <section className="animation-timeline" aria-label="Animation timeline">
      <h4>Moveset · {asset.name}</h4>
      <form onSubmit={createClip} className="animation-row">
        <input name="name" aria-label="Animation name" placeholder="idle, walk, attack…" required maxLength={120} />
        <button type="submit" disabled={create.isPending}>Add clip</button>
      </form>
      {create.isError && <p role="alert" className="form-error">{create.error.message}</p>}
      {clips.isError && <p role="alert" className="form-error">Could not load animations.</p>}
      <div className="animation-row" role="group" aria-label="Animation clips">
        {clips.data?.map((clip) => (
          <button key={clip.id} type="button" aria-pressed={selectedId === clip.id} onClick={() => selectClip(clip)}>
            {clip.name} · {clip.direction}
          </button>
        ))}
      </div>
      {selectedClip && <>
        <div className="animation-row">
          <label>Name <input key={selectedClip.id + selectedClip.name} aria-label="Clip name" maxLength={120} defaultValue={selectedClip.name}
            onBlur={(event) => { if (event.target.value.trim()) void run(() => updateAnimation(selectedClip.id, { name: event.target.value })); }} /></label>
          <label>FPS <input key={selectedClip.id + selectedClip.fps} type="number" min="1" max="60" aria-label="Animation FPS" defaultValue={selectedClip.fps}
            onBlur={(event) => { if (event.target.validity.valid) void run(() => updateAnimation(selectedClip.id, { fps: Number(event.target.value) })); }} /></label>
          <label>Loop <select aria-label="Loop mode" value={selectedClip.loop_mode}
            onChange={(event) => void run(() => updateAnimation(selectedClip.id, { loop_mode: event.target.value as AnimationClip["loop_mode"] }))}>
            <option value="loop">Loop</option><option value="once">Once</option><option value="ping_pong">Ping pong</option>
          </select></label>
          <label>Direction <input key={selectedClip.id + selectedClip.direction} aria-label="Direction" maxLength={32} defaultValue={selectedClip.direction}
            onBlur={(event) => void run(() => updateAnimation(selectedClip.id, { direction: event.target.value }))} /></label>
          <button type="button" onClick={() => void run(async () => { await deleteAnimation(selectedClip.id); setSelectedId(null); })}>Delete clip</button>
        </div>
        <div className="animation-row">
          <label>Add version <select key={versions.data?.map((version) => version.id).join(",") ?? "loading"}
            aria-label="Frame version" id="frame-version" defaultValue={versions.data?.[0]?.id ?? asset.active_version_id ?? ""}>
            {versions.data?.map((version) => <option key={version.id} value={version.id}>v{version.version_number}</option>)}
          </select></label>
          <button type="button" disabled={!versions.data?.length} onClick={() => {
            const versionId = (document.getElementById("frame-version") as HTMLSelectElement).value;
            void run(() => addAnimationFrame(selectedClip.id, versionId));
          }}>Add frame</button>
          <button type="button" disabled={!orderedFrames.length} onClick={() => {
            if (playing) setSelectedFrameId(currentFrame?.id ?? null);
            else setElapsedMs(0);
            setPlaying(!playing);
          }}>{playing ? "Pause" : "Play"}</button>
          <label><input type="checkbox" checked={onionSkin} onChange={(event) => setOnionSkin(event.target.checked)} /> Onion skin</label>
        </div>
        {frames.isError && <p role="alert" className="form-error">Could not load frames.</p>}
        <div className="animation-preview" style={{ width: selectedClip.canvas_width * 4, height: selectedClip.canvas_height * 4 }}>
          {onionSkin && previousFrame && <img className="animation-preview__onion" alt="Previous frame" src={assetVersionContentUrl(previousFrame.asset_version_id)}
            style={{ transform: `translate(${previousFrame.offset_x * 4}px, ${previousFrame.offset_y * 4}px)` }} />}
          {onionSkin && nextFrame && <img className="animation-preview__onion" alt="Next frame" src={assetVersionContentUrl(nextFrame.asset_version_id)}
            style={{ transform: `translate(${nextFrame.offset_x * 4}px, ${nextFrame.offset_y * 4}px)` }} />}
          {currentFrame && <img alt="Current frame" src={assetVersionContentUrl(currentFrame.asset_version_id)}
            style={{ transform: `translate(${currentFrame.offset_x * 4}px, ${currentFrame.offset_y * 4}px)` }} />}
          {currentFrame && <span className="animation-preview__pivot" aria-label="Frame pivot"
            style={{ left: (currentFrame.pivot_x + currentFrame.offset_x) * 4, top: (currentFrame.pivot_y + currentFrame.offset_y) * 4 }} />}
        </div>
        <div className="animation-frames" role="list" aria-label="Frames">
          {orderedFrames.map((frame, index) => (
            <button key={frame.id} type="button" role="listitem" draggable
              onDragStart={() => setDraggedId(frame.id)} onDragOver={(event) => event.preventDefault()}
              onDrop={() => { if (draggedId) moveFrame(draggedId, frame.id); setDraggedId(null); }}
              onClick={() => { setPlaying(false); setSelectedFrameId(frame.id); }}
              aria-current={frame.id === currentFrame?.id ? "true" : undefined}>
              <img alt="" src={assetVersionContentUrl(frame.asset_version_id)} />
              <span>{index + 1} · {frame.duration_ms}ms</span>
            </button>
          ))}
        </div>
        {currentFrame && <div className="animation-frame-fields">
          {(["duration_ms", "pivot_x", "pivot_y", "offset_x", "offset_y"] as const).map((field) => (
            <label key={field}>{field.replace("_", " ")}
              <input key={currentFrame.id + field + currentFrame[field]} type="number" aria-label={field} min={field === "duration_ms" ? 1 : -4096}
                max={field === "duration_ms" ? 60000 : 4096} defaultValue={currentFrame[field]}
                onBlur={(event) => { if (event.target.validity.valid) changeFrame(currentFrame, { [field]: Number(event.target.value) }); }} />
            </label>
          ))}
          <label>Event <input key={currentFrame.id + (currentFrame.event_name ?? "")} aria-label="Event marker" maxLength={80} defaultValue={currentFrame.event_name ?? ""}
            onBlur={(event) => changeFrame(currentFrame, { event_name: event.target.value || null })} /></label>
          <button type="button" onClick={() => void run(() => duplicateAnimationFrame(currentFrame.id))}>Duplicate frame</button>
          <button type="button" disabled={previewIndex === 0} onClick={() => moveFrame(currentFrame.id, orderedFrames[previewIndex - 1].id)}>Move left</button>
          <button type="button" disabled={previewIndex >= orderedFrames.length - 1} onClick={() => moveFrame(currentFrame.id, orderedFrames[previewIndex + 1].id)}>Move right</button>
          <button type="button" onClick={() => void run(() => deleteAnimationFrame(currentFrame.id))}>Delete frame</button>
        </div>}
      </>}
      {error && <p role="alert" className="form-error">{error}</p>}
    </section>
  );
}
