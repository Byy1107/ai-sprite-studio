import { describe, expect, it } from "vitest";

import { applyTool, editorReducer, emptyHistory, screenToPixel, type EditorDocument } from "./editorState";

function blank(width = 4, height = 4): EditorDocument {
  return { width, height, pixels: new Uint8ClampedArray(width * height * 4) };
}

function alphaAt(document: EditorDocument, x: number, y: number) {
  return document.pixels[(y * document.width + x) * 4 + 3];
}

describe("pixel editor state", () => {
  it("maps pointer coordinates accurately at arbitrary zoom", () => {
    expect(screenToPixel(210, 120, { left: 10, top: 20, width: 400, height: 200 }, 4, 4)).toEqual({ x: 2, y: 2 });
  });

  it("draws crisp lines and rectangle edges", () => {
    const line = applyTool(blank(), "line", { x: 0, y: 0 }, { x: 3, y: 3 }, "#ffffff");
    expect([0, 1, 2, 3].map((index) => alphaAt(line, index, index))).toEqual([255, 255, 255, 255]);
    const rectangle = applyTool(blank(), "rectangle", { x: 1, y: 1 }, { x: 3, y: 3 }, "#ffffff");
    expect(alphaAt(rectangle, 1, 1)).toBe(255);
    expect(alphaAt(rectangle, 2, 2)).toBe(0);
  });

  it("fills connected pixels and supports undo and redo", () => {
    const loaded = editorReducer(emptyHistory, { type: "load", document: blank() });
    const filled = applyTool(loaded.present!, "fill", { x: 0, y: 0 }, { x: 0, y: 0 }, "#67b7b2");
    const applied = editorReducer(loaded, { type: "apply", document: filled });
    expect(alphaAt(applied.present!, 3, 3)).toBe(255);
    const undone = editorReducer(applied, { type: "undo" });
    expect(alphaAt(undone.present!, 3, 3)).toBe(0);
    expect(alphaAt(editorReducer(undone, { type: "redo" }).present!, 3, 3)).toBe(255);
  });

  it("erases pixels without smoothing", () => {
    const drawn = applyTool(blank(), "pencil", { x: 1, y: 1 }, { x: 1, y: 1 }, "#ffffff");
    const erased = applyTool(drawn, "eraser", { x: 1, y: 1 }, { x: 1, y: 1 }, "#ffffff");
    expect(alphaAt(erased, 1, 1)).toBe(0);
  });
});
