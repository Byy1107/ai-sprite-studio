import { KeyboardEvent, PointerEvent, useEffect, useReducer, useRef, useState } from "react";
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
const toolShortcuts: Partial<Record<string, DrawingTool | "picker" | "pan" | "select">> = {
  b: "pencil", e: "eraser", i: "picker", f: "fill", l: "line", r: "rectangle", h: "pan", s: "select",
};
const shortcutLabels: Record<DrawingTool | "picker" | "pan" | "select", string> = {
  pencil: "B", eraser: "E", picker: "I", fill: "F", line: "L", rectangle: "R", pan: "H", select: "S",
};

type Draft = { width: number; height: number; pixels: number[] };

function readDraft(key: string, width: number, height: number): Draft | null {
  try {
    const stored = localStorage.getItem(key);
    if (!stored) return null;
    const draft: unknown = JSON.parse(stored);
    if (typeof draft !== "object" || draft === null) return null;
    const candidate = draft as Partial<Draft>;
    if (candidate.width !== width || candidate.height !== height ||
      !Array.isArray(candidate.pixels) || candidate.pixels.length !== width * height * 4 ||
      !candidate.pixels.every((value) => Number.isInteger(value) && value >= 0 && value <= 255)) return null;
    return candidate as Draft;
  } catch {
    return null;
  }
}

export function PixelEditor({ asset }: { asset: Asset }) {
  const queryClient = useQueryClient();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const viewportRef = useRef<HTMLDivElement>(null);
  const dragStart = useRef<PixelPoint | null>(null);
  const panStart = useRef<{ x: number; y: number; left: number; top: number } | null>(null);
  const [history, dispatch] = useReducer(editorReducer, emptyHistory);
  const [tool, setTool] = useState<DrawingTool | "picker" | "pan" | "select">("pencil");
  const [keyboardCursor, setKeyboardCursor] = useState<PixelPoint>({ x: 0, y: 0 });
  const [keyboardAnchor, setKeyboardAnchor] = useState<PixelPoint | null>(null);
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
      const draft = readDraft(draftKey, asset.width, asset.height);
      if (draft) {
        dispatch({ type: "load", document: { ...draft, pixels: new Uint8ClampedArray(draft.pixels) } });
        setUnpublishedChanges(true);
        setMessage("Local draft restored. Publish it to create a new version.");
        return;
      }
      if (!asset.active_version_id) {
        setMessage("No published version or recoverable local draft is available.");
        return;
      }
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
    if (!unpublishedChanges || !history.present) return;
    const document = history.present;
    const persist = () => {
      try {
        localStorage.setItem(draftKey, JSON.stringify({
          width: document.width, height: document.height, pixels: Array.from(document.pixels),
        }));
      } catch {
        setMessage("Autosave failed. Keep this tab open and free browser storage before continuing.");
      }
    };
    const timeout = window.setTimeout(persist, 500);
    window.addEventListener("pagehide", persist);
    return () => {
      window.clearTimeout(timeout);
      window.removeEventListener("pagehide", persist);
    };
  }, [draftKey, history.present, unpublishedChanges]);

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
    try {
      localStorage.setItem(draftKey, JSON.stringify({
        width: history.present.width,
        height: history.present.height,
        pixels: Array.from(history.present.pixels),
      }));
      setMessage("Draft saved locally. It is not a published version yet.");
    } catch {
      setMessage("Draft could not be saved. Free browser storage before closing this tab.");
    }
  }

  function handleCanvasKeyDown(event: KeyboardEvent<HTMLCanvasElement>) {
    if (!history.present) return;
    const offsets: Record<string, PixelPoint> = {
      ArrowLeft: { x: -1, y: 0 }, ArrowRight: { x: 1, y: 0 },
      ArrowUp: { x: 0, y: -1 }, ArrowDown: { x: 0, y: 1 },
    };
    const offset = offsets[event.key];
    if (offset) {
      event.preventDefault();
      event.stopPropagation();
      const width = history.present.width;
      const height = history.present.height;
      setKeyboardCursor((current) => ({
        x: Math.max(0, Math.min(width - 1, current.x + offset.x)),
        y: Math.max(0, Math.min(height - 1, current.y + offset.y)),
      }));
      return;
    }
    if (event.key !== " " && event.key !== "Enter") return;
    event.preventDefault();
    event.stopPropagation();
    const point = {
      x: Math.min(keyboardCursor.x, history.present.width - 1),
      y: Math.min(keyboardCursor.y, history.present.height - 1),
    };
    if (tool === "pan") return;
    if (tool === "picker") {
      setColor(colorAt(history.present, point));
      return;
    }
    if (tool === "line" || tool === "rectangle" || tool === "select") {
      if (!keyboardAnchor) {
        setKeyboardAnchor(point);
        return;
      }
      if (tool === "select") updateSelection(keyboardAnchor, point);
      else {
        dispatch({ type: "apply", document: applyTool(history.present, tool, keyboardAnchor, point, color) });
        setUnpublishedChanges(true);
      }
      setKeyboardAnchor(null);
      return;
    }
    dispatch({ type: "apply", document: applyTool(history.present, tool, point, point, color) });
    setUnpublishedChanges(true);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLElement>) {
    if (event.target instanceof Element && event.target.closest("input, textarea, select, [contenteditable='true']")) return;
    if (event.altKey) return;
    const key = event.key.toLowerCase();
    if (event.ctrlKey || event.metaKey) {
      if (key === "z" && event.shiftKey && history.future.length) {
        event.preventDefault();
        dispatch({ type: "redo" });
      } else if (key === "z" && history.past.length) {
        event.preventDefault();
        dispatch({ type: "undo" });
      } else if (key === "y" && history.future.length) {
        event.preventDefault();
        dispatch({ type: "redo" });
      } else if (key === "s" && history.present) {
        event.preventDefault();
        saveDraft();
      }
      return;
    }
    const shortcutTool = toolShortcuts[key];
    if (event.shiftKey || !shortcutTool) return;
    event.preventDefault();
    setTool(shortcutTool);
    setKeyboardAnchor(null);
  }

  return (
    <section className="pixel-editor" aria-label="Pixel editor" tabIndex={0} onKeyDown={handleKeyDown}>
      <div className="pixel-editor__header">
        <div><h4>Pixel editor</h4><span>{asset.width}×{asset.height} · nearest-neighbor</span></div>
        <div className="editor-actions">
          <button type="button" aria-keyshortcuts="Control+Z" onClick={() => dispatch({ type: "undo" })} disabled={!history.past.length}>Undo</button>
          <button type="button" aria-keyshortcuts="Control+Y" onClick={() => dispatch({ type: "redo" })} disabled={!history.future.length}>Redo</button>
          <button type="button" aria-keyshortcuts="Control+S" onClick={saveDraft} disabled={!history.present}>Save draft</button>
          <button type="button" onClick={() => publish.mutate()} disabled={!history.present || publish.isPending}>Publish version</button>
        </div>
      </div>
      <div className="editor-toolbar" role="toolbar" aria-label="Drawing tools">
        {tools.map((item) => <button type="button" aria-keyshortcuts={shortcutLabels[item.id]} aria-pressed={tool === item.id} key={item.id} onClick={() => { setTool(item.id); setKeyboardAnchor(null); }}>{item.label}</button>)}
      </div>
      <p>Keyboard: B pencil, E eraser, I picker, F fill, L line, R rectangle, H pan, S select. Ctrl+Z undo, Ctrl+Y redo, Ctrl+S save draft.</p>
      <p id={`editor-canvas-help-${asset.id}`}>Focus the canvas, use arrow keys to move one pixel, then Space or Enter to apply the tool. For line, rectangle, or selection, press twice to set both corners. Pan uses pointer or viewport scrolling.</p>
      <div className="editor-layout">
        <aside className="palette-panel">
          <label>Color <input aria-label="Editor color" type="color" value={color} onChange={(event) => setColor(event.target.value)} /></label>
          <div className="palette-swatches">{defaultPalette.map((swatch) => <button aria-label={`Use ${swatch}`} type="button" key={swatch} style={{ background: swatch }} onClick={() => setColor(swatch)} />)}</div>
          <label>Zoom <input aria-label="Editor zoom" type="range" min="4" max="32" step="2" value={zoom} onChange={(event) => setZoom(Number(event.target.value))} /></label>
          <label><input type="checkbox" checked={grid} onChange={(event) => setGrid(event.target.checked)} /> Grid</label>
        </aside>
        <div className="editor-viewport" ref={viewportRef} role="region" aria-label="Canvas viewport" tabIndex={0}>
          <div className="canvas-wrap" style={{ width: asset.width * zoom, height: asset.height * zoom }}>
            <canvas
              ref={canvasRef}
              aria-label="Pixel canvas"
              aria-describedby={`editor-canvas-help-${asset.id}`}
              tabIndex={0}
              style={{ width: asset.width * zoom, height: asset.height * zoom }}
              onKeyDown={handleCanvasKeyDown}
              onPointerDown={pointerDown}
              onPointerMove={pointerMove}
              onPointerUp={pointerUp}
              onPointerLeave={pointerUp}
            />
            <div className="editor-keyboard-cursor" style={{
              left: keyboardCursor.x * zoom, top: keyboardCursor.y * zoom,
              width: zoom, height: zoom,
            }} />
            {grid ? <div className="pixel-grid" style={{ backgroundSize: `${zoom}px ${zoom}px` }} /> : null}
            {selection ? <div className="editor-selection" style={{
              left: selection.x * zoom, top: selection.y * zoom,
              width: selection.width * zoom, height: selection.height * zoom,
            }} /> : null}
          </div>
        </div>
      </div>
      <p aria-live="polite">Keyboard cursor: {keyboardCursor.x + 1}, {keyboardCursor.y + 1}{keyboardAnchor ? "; first corner set" : ""}.</p>
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
