export type PixelPoint = { x: number; y: number };
export type DrawingTool = "pencil" | "eraser" | "fill" | "line" | "rectangle";

export type EditorDocument = {
  width: number;
  height: number;
  pixels: Uint8ClampedArray;
};

export type EditorHistory = {
  past: EditorDocument[];
  present: EditorDocument | null;
  future: EditorDocument[];
};

export type EditorAction =
  | { type: "load"; document: EditorDocument }
  | { type: "apply"; document: EditorDocument }
  | { type: "undo" }
  | { type: "redo" };

export const emptyHistory: EditorHistory = { past: [], present: null, future: [] };

export function editorReducer(state: EditorHistory, action: EditorAction): EditorHistory {
  if (action.type === "load") {
    return { past: [], present: action.document, future: [] };
  }
  if (action.type === "apply") {
    if (!state.present || documentsEqual(state.present, action.document)) return state;
    return { past: [...state.past, state.present], present: action.document, future: [] };
  }
  if (action.type === "undo") {
    const previous = state.past.at(-1);
    if (!previous || !state.present) return state;
    return {
      past: state.past.slice(0, -1),
      present: previous,
      future: [state.present, ...state.future],
    };
  }
  const next = state.future[0];
  if (!next || !state.present) return state;
  return {
    past: [...state.past, state.present],
    present: next,
    future: state.future.slice(1),
  };
}

export function documentFromImageData(image: ImageData): EditorDocument {
  return { width: image.width, height: image.height, pixels: new Uint8ClampedArray(image.data) };
}

export function documentToImageData(document: EditorDocument): ImageData {
  return new ImageData(new Uint8ClampedArray(document.pixels), document.width, document.height);
}

export function screenToPixel(
  clientX: number,
  clientY: number,
  rect: Pick<DOMRect, "left" | "top" | "width" | "height">,
  width: number,
  height: number,
): PixelPoint {
  return {
    x: Math.max(0, Math.min(width - 1, Math.floor(((clientX - rect.left) / rect.width) * width))),
    y: Math.max(0, Math.min(height - 1, Math.floor(((clientY - rect.top) / rect.height) * height))),
  };
}

export function colorAt(document: EditorDocument, point: PixelPoint): string {
  const index = pixelIndex(document, point);
  return `#${[document.pixels[index], document.pixels[index + 1], document.pixels[index + 2]]
    .map((channel) => channel.toString(16).padStart(2, "0"))
    .join("")}`;
}

export function applyTool(
  document: EditorDocument,
  tool: DrawingTool,
  start: PixelPoint,
  end: PixelPoint,
  color: string,
): EditorDocument {
  const next = { ...document, pixels: new Uint8ClampedArray(document.pixels) };
  const rgba = tool === "eraser" ? [0, 0, 0, 0] : parseHex(color);
  if (tool === "fill") {
    floodFill(next, start, rgba);
  } else if (tool === "rectangle") {
    drawRectangle(next, start, end, rgba);
  } else {
    drawLine(next, start, tool === "pencil" || tool === "eraser" ? end : end, rgba);
  }
  return next;
}

function drawRectangle(
  document: EditorDocument,
  start: PixelPoint,
  end: PixelPoint,
  color: number[],
) {
  const left = Math.min(start.x, end.x);
  const right = Math.max(start.x, end.x);
  const top = Math.min(start.y, end.y);
  const bottom = Math.max(start.y, end.y);
  drawLine(document, { x: left, y: top }, { x: right, y: top }, color);
  drawLine(document, { x: right, y: top }, { x: right, y: bottom }, color);
  drawLine(document, { x: right, y: bottom }, { x: left, y: bottom }, color);
  drawLine(document, { x: left, y: bottom }, { x: left, y: top }, color);
}

function drawLine(document: EditorDocument, start: PixelPoint, end: PixelPoint, color: number[]) {
  let x = start.x;
  let y = start.y;
  const deltaX = Math.abs(end.x - start.x);
  const deltaY = -Math.abs(end.y - start.y);
  const stepX = start.x < end.x ? 1 : -1;
  const stepY = start.y < end.y ? 1 : -1;
  let error = deltaX + deltaY;
  while (true) {
    setPixel(document, { x, y }, color);
    if (x === end.x && y === end.y) break;
    const doubled = error * 2;
    if (doubled >= deltaY) {
      error += deltaY;
      x += stepX;
    }
    if (doubled <= deltaX) {
      error += deltaX;
      y += stepY;
    }
  }
}

function floodFill(document: EditorDocument, start: PixelPoint, color: number[]) {
  const target = pixel(document, start);
  if (target.every((value, index) => value === color[index])) return;
  const queue = [start];
  const visited = new Set<string>();
  while (queue.length) {
    const point = queue.pop()!;
    const key = `${point.x}:${point.y}`;
    if (visited.has(key) || !pixel(document, point).every((value, index) => value === target[index])) {
      continue;
    }
    visited.add(key);
    setPixel(document, point, color);
    if (point.x > 0) queue.push({ x: point.x - 1, y: point.y });
    if (point.x < document.width - 1) queue.push({ x: point.x + 1, y: point.y });
    if (point.y > 0) queue.push({ x: point.x, y: point.y - 1 });
    if (point.y < document.height - 1) queue.push({ x: point.x, y: point.y + 1 });
  }
}

function pixel(document: EditorDocument, point: PixelPoint): number[] {
  const index = pixelIndex(document, point);
  return Array.from(document.pixels.slice(index, index + 4));
}

function setPixel(document: EditorDocument, point: PixelPoint, color: number[]) {
  document.pixels.set(color, pixelIndex(document, point));
}

function pixelIndex(document: EditorDocument, point: PixelPoint): number {
  return (point.y * document.width + point.x) * 4;
}

function parseHex(color: string): number[] {
  return [
    Number.parseInt(color.slice(1, 3), 16),
    Number.parseInt(color.slice(3, 5), 16),
    Number.parseInt(color.slice(5, 7), 16),
    255,
  ];
}

function documentsEqual(left: EditorDocument, right: EditorDocument): boolean {
  if (left.width !== right.width || left.height !== right.height) return false;
  return left.pixels.every((value, index) => value === right.pixels[index]);
}
