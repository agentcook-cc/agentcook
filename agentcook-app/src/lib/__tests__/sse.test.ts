import { describe, expect, it } from "vitest";
import { readSseJson, SseParser } from "../sse";

function streamOf(...chunks: string[]): ReadableStream<Uint8Array> {
  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(new TextEncoder().encode(chunk));
      controller.close();
    },
  });
}

describe("SseParser", () => {
  it("splits events on blank lines and joins multi-line data", () => {
    const parser = new SseParser();
    expect(parser.push('data: {"a":1}\n\ndata: line1\ndata: line2\n\n')).toEqual([
      { event: "message", data: '{"a":1}', id: undefined },
      { event: "message", data: "line1\nline2", id: undefined },
    ]);
  });

  it("buffers partial events across chunks", () => {
    const parser = new SseParser();
    expect(parser.push('data: {"par')).toEqual([]);
    expect(parser.push('t":2}\n')).toEqual([]);
    expect(parser.push("\n")).toEqual([{ event: "message", data: '{"part":2}', id: undefined }]);
  });

  it("ignores comments (keep-alive pings) and handles CRLF", () => {
    const parser = new SseParser();
    expect(parser.push(": ping\r\n\r\nevent: x\r\nid: 7\r\ndata: y\r\n\r\n")).toEqual([
      { event: "x", data: "y", id: "7" },
    ]);
  });

  it("flushes an unterminated trailing event", () => {
    const parser = new SseParser();
    parser.push("data: tail");
    expect(parser.flush()).toEqual([{ event: "message", data: "tail", id: undefined }]);
  });
});

describe("readSseJson", () => {
  it("yields parsed JSON frames, skipping non-JSON and stopping at [DONE]", async () => {
    const out: unknown[] = [];
    for await (const frame of readSseJson(
      streamOf('data: {"n":1}\n\ndata: not-json\n\n', 'data: {"n":2}\n\ndata: [DONE]\n\ndata: {"n":3}\n\n'),
    )) {
      out.push(frame);
    }
    expect(out).toEqual([{ n: 1 }, { n: 2 }]);
  });
});
