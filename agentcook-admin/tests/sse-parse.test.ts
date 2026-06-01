import { describe, it, expect } from "vitest";
import { parseSseLines } from "@/composables/useSseStream";

describe("parseSseLines · Day 28 SSE parser", () => {
  it("returns empty for input without trailing newline (buffering)", () => {
    const r = parseSseLines("data: hello");
    expect(r.content).toBe("");
    expect(r.done).toBe(false);
    expect(r.remainder).toBe("data: hello");
  });

  it("extracts content from a complete data line ending in newline", () => {
    const r = parseSseLines('data: {"content":"hi"}\n');
    expect(r.content).toBe("hi");
    expect(r.done).toBe(false);
    expect(r.remainder).toBe("");
  });

  it("accepts delta and text fallback fields", () => {
    const r = parseSseLines(
      'data: {"delta":"a"}\n' +
        'data: {"text":"b"}\n' +
        'data: {"content":"c"}\n',
    );
    expect(r.content).toBe("abc");
  });

  it("treats raw payload as content when JSON parse fails", () => {
    const r = parseSseLines("data: raw chunk\n");
    expect(r.content).toBe("raw chunk");
  });

  it("ignores comment lines and empty lines", () => {
    const r = parseSseLines(": ping\n\ndata: {\"content\":\"a\"}\n");
    expect(r.content).toBe("a");
  });

  it("flips done=true on [DONE] sentinel", () => {
    const r = parseSseLines('data: {"content":"x"}\ndata: [DONE]\n');
    expect(r.content).toBe("x");
    expect(r.done).toBe(true);
  });

  it("preserves partial trailing line as remainder for next chunk", () => {
    const r = parseSseLines(
      'data: {"content":"complete"}\ndata: {"content":"par',
    );
    expect(r.content).toBe("complete");
    expect(r.done).toBe(false);
    expect(r.remainder).toBe('data: {"content":"par');
  });
});
