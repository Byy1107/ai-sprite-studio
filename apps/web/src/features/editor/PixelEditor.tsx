import { PointerEvent, useEffect, useReducer, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  assetVersionContentUrl,
  createGenerationJob,
  getAICapabilities,
  listAssetVersions,
  publishManualVersion,
  type Asset,
} from "../../lib/api";
import {
  applyTool,
  colorAt,
  documentFromImageData,
  documentToImageData,
  editorReducer,
  emptyHistory,
  screenToPixel,
  type DrawingTool,
  type PixelPoint,
} from "./editorState";

const tools: Array<{ id: DrawingTool | "picker" | "pan" | "select"; label: string }> = [
  { id: "pencil", label: "Pencil" },
  { id: "eraser", label: "Eraser" },
  { id: "picker", label: "Picker" },
  { id: "fill", label: "Fill" },
  { id: "line", label: "Line" },
  { id: "rectangle", label: "Rectangle" },
  { id: "pan", label: "Pan" },
  { id: "select", label: "Select region" },
];

const defaultPalette = ["#0b0d17", "#252b47", "#49506b", "#a7aec4", "#d8d2c4", "#b28a45", "#8f4938", "#67b7b2"];

type Draft = { width: number; height: number; pixels: number[] };

export function PixelEditor({ asset }: { asset: Asset }) {
  const queryClient = useQueryClient();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const viewportRef = useRef<HTMLDivElement>(null);
  const dragStart = useRef<PixelPoint | null>(null);
  const panStart = useRef<{ x: number; y: number; left: number; top: number } | null>(null);
  const [history, dispatch] = useReducer(editorReducer, emptyHistory);
  const [tool, setTool] = useState<DrawingTool | "picker" | "pan" | "select">("pencil");
  const [color, setColor] = useState("#67b7b2");
  const [zoom, setZoom] = useState(16);
  const [grid, setGrid] = useState(true);
  const [message, setMessage] = useState("Loading active version…");
  const [selection, setSelection] = useState<{
    x: number; y: number; width: number; height: number;
  } | null>(null);
  const [aiPrompt, setAIPrompt] = useState("pixel art sprite variation");
  const [aiSeed, setAISeed] = useState(1);
  const [unpublishedChanges, setUnpublishedChanges] = useState(false);
  const draftKey = `ai-sprite-studio:draft:${asset.id}`;
  const versionsQuery = useQuery({
    queryKey: ["asset-versions", asset.id],
    queryFn: ({ signal }) => listAssetVersions(asset.id, signal),
  });
  const capabilitiesQuery = useQuery({
    queryKey: ["ai-capabilities"],
    queryFn: ({ signal }) => getAICapabilities(signal),
    retry: false,
  });
  const editAvailable = capabilitiesQuery.data?.enabled_features?.variation === true;
  const sourceVersionId = versionsQuery.data?.[0]?.id;

  useEffect(() => {
    let canceled = false;
    async function load() {
      const stored = localStorage.getItem(draftKey);
      if (stored) {
        const draft = JSON.parse(stored) as Draft;
        if (draft.width === asset.width && draft.height === asset.height) {
          dispatch({ type: "load", document: { ...draft, pixels: new Uint8ClampedArray(draft.pixels) } });
          setUnpublishedChanges(true);
          setMessage("Local draft restored.");
          return;
        }
      }
      if (!asset.active_version_id) return;
      const image = new Image();
      image.crossOrigin = "anonymous";
      image.src = assetVersionContentUrl(asset.active_version_id);
      await image.decode();
      if (canceled) return;
      const canvas = document.createElement("canvas");
      canvas.width = asset.width;
      canvas.height = asset.height;
      const context = canvas.getContext("2d", { willReadFrequently: true });
      if (!context) throw new Error("Canvas 2D is not available.");
      context.imageSmoothingEnabled = false;
      context.drawImage(image, 0, 0);
      dispatch({ type: "load", document: documentFromImageData(context.getImageData(0, 0, asset.width, asset.height)) });
      setMessage("Active version loaded.");
    }
    load().catch((error: unknown) => setMessage(error instanceof Error ? error.message : "Could not load image."));
    return () => { canceled = true; };
  }, [asset.active_version_id, asset.height, asset.width, draftKey]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !history.present) return;
    canvas.width = history.present.width;
    canvas.height = history.present.height;
    const context = canvas.getContext("2d");
    if (!context) return;
    context.imageSmoothingEnabled = false;
    context.clearRect(0, 0, canvas.width, canvas.height);
    context.putImageData(documentToImageData(history.present), 0, 0);
  }, [history.present]);

  const publish = useMutation({
    mutationFn: async () => {
      const canvas = canvasRef.current;
      if (!canvas) throw new Error("Editor canvas is not ready.");
      const blob = await new Promise<Blob>((resolve, reject) =>
        canvas.toBlob((result) => result ? resolve(result) : reject(new Error("PNG export failed.")), "image/png"),
      );
      return publishManualVersion(asset.id, blob, "Manual pixel edit");
    },
    onSuccess: () => {
      localStorage.removeItem(draftKey);
      setUnpublishedChanges(false);
      setSelection(null);
      setMessage("Manual edit published as a new version.");
      queryClient.invalidateQueries({ queryKey: ["asset-versions", asset.id] });
      queryClient.invalidateQueries({ queryKey: ["assets", asset.project_id] });
    },
    onError: (error) => setMessage(error.message),
  });

  const aiEdit = useMutation({
    mutationFn: (operation: "variation" | "inpaint") => {
      if (!sourceVersionId) throw new Error("Save an asset version before AI editing.");
      if (operation === "inpaint" && !selection) throw new Error("Select a region first.");
      return createGenerationJob({
        project_id: asset.project_id,
        asset_id: asset.id,
        reference_asset_id: asset.id,
        reference_version_id: sourceVersionId,
        operation,
        mask_x: operation === "inpaint" ? selection!.x : null,
        mask_y: operation === "inpaint" ? selection!.y : null,
        mask_width: operation === "inpaint" ? selection!.width : null,
        mask_height: operation === "inpaint" ? selection!.height : null,
        prompt: aiPrompt.trim(),
        asset_type: asset.asset_type,
        style: asset.style === "micro_pixel" ? "micro_pixel" : "eight_bit",
        width: asset.width,
        height: asset.height,
        seed: aiSeed,
      });
    },
    onSuccess: (job) => {
      setMessage(`AI edit queued: ${job.id}. Review the candidate in project generation jobs.`);
      queryClient.invalidateQueries({ queryKey: ["generation-jobs", asset.project_id] });
    },
    onError: (error) => setMessage(error.message),
  });

  function updateSelection(start: PixelPoint, end: PixelPoint) {
    setSelection({
      x: Math.min(start.x, end.x), y: Math.min(start.y, end.y),
      width: Math.abs(start.x - end.x) + 1,
      height: Math.abs(start.y - end.y) + 1,
    });
  }

  function pointFromEvent(event: PointerEvent<HTMLCanvasElement>): PixelPoint | null {
    if (!history.present) return null;
    return screenToPixel(event.clientX, event.clientY, event.currentTarget.getBoundingClientRect(), history.present.width, history.present.height);
  }

  function pointerDown(event: PointerEvent<HTMLCanvasElement>) {
    if (!history.present) return;
    if (tool === "pan") {
      const viewport = viewportRef.current;
      if (viewport) panStart.current = { x: event.clientX, y: event.clientY, left: viewport.scrollLeft, top: viewport.scrollTop };
      return;
    }
    const point = pointFromEvent(event);
    if (!point) return;
    if (tool === "picker") {
      setColor(colorAt(history.present, point));
      return;
    }
    dragStart.current = point;
    if (tool === "select") {
      updateSelection(point, point);
      return;
    }
    if (tool === "fill") {
      dispatch({ type: "apply", document: applyTool(history.present, tool, point, point, color) });
      setUnpublishedChanges(true);
      dragStart.current = null;
    }
  }

  function pointerMove(event: PointerEvent<HTMLCanvasElement>) {
    if (tool === "select" && dragStart.current) {
      const point = pointFromEvent(event);
      if (point) updateSelection(dragStart.current, point);
      return;
    }
    if (tool !== "pan" || !panStart.current || !viewportRef.current) return;
    viewportRef.current.scrollLeft = panStart.current.left - (event.clientX - panStart.current.x);
    viewportRef.current.scrollTop = panStart.current.top - (event.clientY - panStart.current.y);
  }

  function pointerUp(event: PointerEvent<HTMLCanvasElement>) {
    panStart.current = null;
    if (tool === "select" && dragStart.current) {
      const end = pointFromEvent(event);
      if (end) updateSelection(dragStart.current, end);
      dragStart.current = null;
      return;
    }
    if (!history.present || !dragStart.current || tool === "picker" || tool === "pan" || tool === "fill" || tool === "select") return;
    const end = pointFromEvent(event);
    if (end) {
      dispatch({ type: "apply", document: applyTool(history.present, tool, dragStart.current, end, color) });
      setUnpublishedChanges(true);
    }
    dragStart.current = null;
  }

  function saveDraft() {
    if (!history.present) return;
    localStorage.setItem(draftKey, JSON.stringify({
      width: history.present.width,
      height: history.present.height,
      pixels: Array.from(history.present.pixels),
    }));
    setMessage("Draft saved locally. It is not a published version yet.");
  }

  return (
    <section className="pixel-editor" aria-label="Pixel editor">
      <div className="pixel-editor__header">
        <div><h4>Pixel editor</h4><span>{asset.width}×{asset.height} · nearest-neighbor</span></div>
        <div className="editor-actions">
          <button type="button" onClick={() => dispatch({ type: "undo" })} disabled={!history.past.length}>Undo</button>
          <button type="button" onClick={() => dispatch({ type: "redo" })} disabled={!history.future.length}>Redo</button>
          <button type="button" onClick={saveDraft} disabled={!history.present}>Save draft</button>
          <button type="button" onClick={() => publish.mutate()} disabled={!history.present || publish.isPending}>Publish version</button>
        </div>
      </div>
      <div className="editor-toolbar" role="toolbar" aria-label="Drawing tools">
        {tools.map((item) => <button type="button" aria-pressed={tool === item.id} key={item.id} onClick={() => setTool(item.id)}>{item.label}</button>)}
      </div>
      <div className="editor-layout">
        <aside className="palette-panel">
          <label>Color <input aria-label="Editor color" type="color" value={color} onChange={(event) => setColor(event.target.value)} /></label>
          <div className="palette-swatches">{defaultPalette.map((swatch) => <button aria-label={`Use ${swatch}`} type="button" key={swatch} style={{ background: swatch }} onClick={() => setColor(swatch)} />)}</div>
          <label>Zoom <input aria-label="Editor zoom" type="range" min="4" max="32" step="2" value={zoom} onChange={(event) => setZoom(Number(event.target.value))} /></label>
          <label><input type="checkbox" checked={grid} onChange={(event) => setGrid(event.target.checked)} /> Grid</label>
        </aside>
        <div className="editor-viewport" ref={viewportRef}>
          <div className="canvas-wrap" style={{ width: asset.width * zoom, height: asset.height * zoom }}>
            <canvas
              ref={canvasRef}
              aria-label="Pixel canvas"
              style={{ width: asset.width * zoom, height: asset.height * zoom }}
              onPointerDown={pointerDown}
              onPointerMove={pointerMove}
              onPointerUp={pointerUp}
              onPointerLeave={pointerUp}
            />
            {grid ? <div className="pixel-grid" style={{ backgroundSize: `${zoom}px ${zoom}px` }} /> : null}
            {selection ? <div className="editor-selection" style={{
              left: selection.x * zoom, top: selection.y * zoom,
              width: selection.width * zoom, height: selection.height * zoom,
            }} /> : null}
          </div>
        </div>
      </div>
      <div className="editor-ai-edit">
        <h5>AI-assisted edit</h5>
        <p>Uses the latest published version. Publish manual edits before queuing. Generated candidates never replace the active version until accepted.</p>
        <label>AI edit prompt <input aria-label="AI edit prompt" maxLength={1000} value={aiPrompt} onChange={(event) => setAIPrompt(event.target.value)} /></label>
        <label>Seed <input aria-label="AI edit seed" type="number" min="0" max="2147483647" value={aiSeed} onChange={(event) => setAISeed(Number(event.target.value))} /></label>
        <button type="button" disabled={!editAvailable || !sourceVersionId || !history.present || unpublishedChanges || !aiPrompt.trim() || aiEdit.isPending}
          onClick={() => aiEdit.mutate("variation")}>Generate variation</button>
        <button type="button" disabled={!capabilitiesQuery.data?.enabled_features?.inpaint || !selection || !sourceVersionId || !history.present || unpublishedChanges || !aiPrompt.trim() || aiEdit.isPending}
          onClick={() => aiEdit.mutate("inpaint")}>Inpaint selection</button>
        {capabilitiesQuery.isError || !editAvailable ? <p>Local ComfyUI image-edit nodes are unavailable.</p> : null}
        {unpublishedChanges ? <p>Publish your current manual changes before AI editing.</p> : null}
      </div>
      <p className="editor-status" aria-live="polite">{message}</p>
    </section>
  );
}
