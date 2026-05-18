import { describe, it, expect } from "vitest";
import { readdirSync, existsSync } from "node:fs";
import { join } from "node:path";

const tokensDir = join(__dirname, "..", "tokens");

describe("design tokens source files", () => {
  it("tokens/ directory exists", () => {
    expect(existsSync(tokensDir)).toBe(true);
  });

  it("contains at least one .json token file", () => {
    const files = readdirSync(tokensDir).filter((f) => f.endsWith(".json"));
    expect(files.length).toBeGreaterThan(0);
  });
});
