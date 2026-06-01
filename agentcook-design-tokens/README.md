# @agentcook-cc/design-tokens

> Shared design system for agentcook — single source of truth for color,
> typography, spacing, radius, shadow, and motion across the Vue 3 admin
> and the React 19 chat app.

**Status: v1.0.0** — frozen for Phase 4 release. Tokens, build pipeline,
and Storybook coverage are stable; new tokens land via the proposal flow
in [Contributing](#contributing).

## What this package gives you

- 6 token domains in `tokens/*.json` — atomic + semantic + dark-mode
- Compiled outputs for 4 consumers via Style Dictionary:
  - **CSS variables** (`dist/css/variables.css`) — admin + app shared
  - **Element Plus theme** (`dist/element-plus/`) — admin
  - **Tailwind preset** (`dist/tailwind/preset.js`) — app
  - **Figma tokens** (`dist/figma/tokens.json`) — design hand-off
- Storybook 8 explorer covering every token + a few component
  previews, runnable locally with `pnpm storybook`

## Layout

```
agentcook-design-tokens/
├── tokens/
│   ├── color.json            ← atomic palette (10 shades × 6 hues)
│   ├── color.dark.json       ← dark-mode overrides
│   ├── color.semantic.json   ← text.primary / bg.surface / border.subtle
│   ├── typography.json       ← font families, sizes, weights, line heights
│   ├── spacing.json          ← 4px-based scale, 0–96
│   ├── radius.json           ← sm/md/lg/full
│   ├── shadow.json           ← elevation 1–5
│   └── motion.json           ← duration + easing
├── stories/                  ← Storybook stories (data-driven from tokens)
├── style-dictionary.config.mjs
├── .storybook/
└── dist/                     ← build output (committed for CDN serving)
```

## Variable cheat-sheet

The full list is in `dist/css/variables.css`. Highlights:

| Domain | Examples |
|--------|----------|
| Color (atomic) | `--color-primary-500`, `--color-neutral-900`, `--color-success-50` |
| Color (semantic) | `--color-text-primary`, `--color-bg-surface`, `--color-border-subtle` |
| Typography | `--font-family-sans`, `--font-size-md`, `--font-weight-bold`, `--line-height-tight` |
| Spacing | `--space-1` (4px) … `--space-24` (96px) |
| Radius | `--radius-sm` (2px) / `--radius-md` (4px) / `--radius-lg` (8px) / `--radius-full` (9999px) |
| Shadow | `--shadow-1` … `--shadow-5` (Material-style elevation) |
| Motion | `--duration-fast` (150ms) / `--easing-standard` (cubic-bezier) |

Both admin and app are guaranteed to render the same pixel values for
the same token — verified by Storybook visual diffs.

## Usage

### Admin (Vue 3 + Element Plus)

```ts
// src/main.ts
import "@agentcook-cc/design-tokens/dist/css/variables.css";
import "@agentcook-cc/design-tokens/dist/element-plus/index.css"; // optional theme override
```

```vue
<style scoped>
.card { color: var(--color-text-primary); padding: var(--space-4); }
</style>
```

### App (React 19 + Tailwind)

```ts
// src/main.tsx
import "@agentcook-cc/design-tokens/dist/css/variables.css";
```

```js
// tailwind.config.js
import preset from "@agentcook-cc/design-tokens/dist/tailwind/preset.js";
export default { presets: [preset], content: ["./src/**/*.{ts,tsx}"] };
```

### Modifying tokens

```bash
# 1. Edit tokens/*.json
# 2. Rebuild outputs
pnpm --filter @agentcook-cc/design-tokens build
# 3. Commit dist/ alongside the source change so consumers don't need to build
```

## Local development

```bash
pnpm install                                                    # install workspace
pnpm --filter @agentcook-cc/design-tokens storybook            # explorer on :6006
pnpm --filter @agentcook-cc/design-tokens build                # regenerate dist/
pnpm --filter @agentcook-cc/design-tokens build-storybook      # static export
pnpm --filter @agentcook-cc/design-tokens typecheck            # tsc --noEmit
pnpm --filter @agentcook-cc/design-tokens test                 # vitest
```

## Design principles

1. **Atomic → Semantic → Component three layers.** Components consume
   semantic tokens (`--color-text-primary`), semantic tokens map to
   atomic ones (`--color-neutral-900`). Never hard-code atomic tokens
   in component code.
2. **Single source of truth.** Token edits happen only in
   `tokens/*.json`. CSS / Element Plus / Tailwind / Figma outputs
   regenerate from there.
3. **Dark mode is a token concern.** `color.dark.json` overrides ship
   the dark palette; consumers toggle by adding a `.theme-dark` class on
   `<html>`.
4. **Zero cognitive cost across stacks.** Vue and React surfaces look
   identical for the same token because they read from the same CSS
   variables file.

## Versioning

This package follows SemVer. v1.0.0 freezes the public token names — any
rename is a breaking change. Adding new tokens or shades is a minor
release. Fixing computed values (e.g. dark-mode contrast adjustments)
that don't break consumers is a patch release.

## Contributing

To propose a new token:

1. Open an issue describing the use-case and proposed name (must follow
   the existing `domain-role-shade` convention).
2. Add the JSON entry, regenerate `dist/`, update Storybook coverage.
3. Open a PR that references the issue. At least one designer + one
   frontend engineer must sign off.

Larger restructurings (e.g. introducing a new color hue) need an ADR
under `docs/adr/`.

## License

Apache-2.0. See repository LICENSE.
