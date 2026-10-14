/**
 * Minimal, spec-compliant Server-Sent Events parser for fetch() bodies.
 *
 * `EventSource` can't POST or send an Authorization header, so chat uses
 * fetch + this parser. Events are separated by a blank line; `data:`
 * lines within one event are joined with "\n"; comment lines (": ping")
 * are keep-alives and ignored; CRLF and CR line endings are accepted.
 */

export interface SseEvent {
  event: string;
  data: string;
  id?: string;
}

export class SseParser {
  private buffer = "";

  /** Feed a decoded chunk; returns the events completed by it. */
  push(chunk: string): SseEvent[] {
    this.buffer += chunk.replace(/\r\n?/g, "\n");
    const events: SseEvent[] = [];
    let boundary = this.buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const block = this.buffer.slice(0, boundary);
      this.buffer = this.buffer.slice(boundary + 2);
      const event = parseBlock(block);
      if (event) events.push(event);
      boundary = this.buffer.indexOf("\n\n");
    }
    return events;
  }

  /** Flush a trailing event that wasn't terminated by a blank line. */
  flush(): SseEvent[] {
    const rest = this.buffer;
    this.buffer = "";
    const event = rest.trim() ? parseBlock(rest) : null;
    return event ? [event] : [];
  }
}

function parseBlock(block: string): SseEvent | null {
  const data: string[] = [];
  let event = "message";
  let id: string | undefined;
  for (const line of block.split("\n")) {
    if (!line || line.startsWith(":")) continue;
    const colon = line.indexOf(":");
    const field = colon === -1 ? line : line.slice(0, colon);
    let value = colon === -1 ? "" : line.slice(colon + 1);
    if (value.startsWith(" ")) value = value.slice(1);
    if (field === "data") data.push(value);
    else if (field === "event") event = value;
    else if (field === "id") id = value;
  }
  if (data.length === 0) return null;
  return { event, data: data.join("\n"), id };
}

/** Iterate parsed JSON payloads from a fetch Response body. */
export async function* readSseJson<T>(body: ReadableStream<Uint8Array>, signal?: AbortSignal): AsyncGenerator<T> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  const parser = new SseParser();
  try {
    while (true) {
      if (signal?.aborted) return;
      const { done, value } = await reader.read();
      const events = done ? parser.flush() : parser.push(decoder.decode(value, { stream: true }));
      for (const event of events) {
        if (event.data === "[DONE]") return;
        try {
          yield JSON.parse(event.data) as T;
        } catch {
          // Non-JSON data lines are not part of the protocol; skip them.
        }
      }
      if (done) return;
    }
  } finally {
    reader.releaseLock();
  }
}
