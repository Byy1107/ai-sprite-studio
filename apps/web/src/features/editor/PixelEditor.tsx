import { PointerEvent, useEffect, useReducer, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
  assetVersionContentUrl,
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

const tools: Array<{ id: DrawingTool | "picker" | "pan"; label: string }> = [
  { id: "pencil", label: "Pencil" },
  { id: "eraser", label: "Eraser" },
  { id: "picker", label: "Picker" },
  { id: "fill", label: "Fill" },
  { id: "line", label: "Line" },
  { id: "rectangle", label: "Rectangle" },
  { id: "pan", label: "Pan" },
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
  const [tool, setTool] = useState<DrawingTool | "picker" | "pan">("pencil");
  const [color, setColor] = useState("#67b7b2");
  const [zoom, setZoom] = useState(16);
  const [grid, setGrid] = useState(true);
  const [message, setMessage] = useState("Loading active version…");
  const draftKey = `ai-sprite-studio:draft:${asset.id}`;

  useEffect(() => {
    let canceled = false;
    async function load() {
      const stored = localStorage.getItem(draftKey);
      if (stored) {
        const draft = JSON.parse(stored) as Draft;
        if (draft.width === asset.width && draft.height === asset.height) {
          dispatch({ type: "load", document: { ...draft, pixels: new Uint8ClampedArray(draft.pixels) } });
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
      setMessage("Manual edit published as a new version.");
      queryClient.invalidateQueries({ queryKey: ["asset-versions", asset.id] });
      queryClient.invalidateQueries({ queryKey: ["assets", asset.project_id] });
    },
    onError: (error) => setMessage(error.message),
  });

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
    if (tool === "fill") {
      dispatch({ type: "apply", document: applyTool(history.present, tool, point, point, color) });
      dragStart.current = null;
    }
  }

  function pointerMove(event: PointerEvent<HTMLCanvasElement>) {
    if (tool !== "pan" || !panStart.current || !viewportRef.current) return;
    viewportRef.current.scrollLeft = panStart.current.left - (event.clientX - panStart.current.x);
    viewportRef.current.scrollTop = panStart.current.top - (event.clientY - panStart.current.y);
  }

  function pointerUp(event: PointerEvent<HTMLCanvasElement>) {
    panStart.current = null;
    if (!history.present || !dragStart.current || tool === "picker" || tool === "pan" || tool === "fill") return;
    const end = pointFromEvent(event);
    if (end) dispatch({ type: "apply", document: applyTool(history.present, tool, dragStart.current, end, color) });
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
          </div>
        </div>
      </div>
      <p className="editor-status" aria-live="polite">{message}</p>
    </section>
  );
}
