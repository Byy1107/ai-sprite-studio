import { expect, it } from "vitest";

import { applyTool, editorReducer, emptyHistory, type EditorDocument } from "./editorState";

it("profiles representative 128-pixel editing without a timing assertion", () => {
  let document: EditorDocument = {
    width: 128,
    height: 128,
    pixels: new Uint8ClampedArray(128 * 128 * 4),
  };
  let history = editorReducer(emptyHistory, { type: "load", document });
  const started = performance.now();
  for (let stroke = 0; stroke < 100; stroke += 1) {
    const coordinate = stroke % 128;
    document = applyTool(document, "pencil", { x: 0, y: coordinate }, { x: 127, y: coordinate }, "#67b7b2");
    history = editorReducer(history, { type: "apply", document });
  }
  const elapsed = performance.now() - started;

  expect(history.past).toHaveLength(100);
  expect(history.present?.pixels[(99 * 128 + 127) * 4 + 3]).toBe(255);
  console.info(`Sprint 10 editor profile: 100 strokes on 128×128 in ${elapsed.toFixed(1)} ms`);
});
