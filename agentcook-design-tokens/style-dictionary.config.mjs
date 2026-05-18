/**
 * Style Dictionary build config (ESM).
 *
 * 重命名自 style-dictionary.config.js (CJS) → .mjs (ESM,2026-05-18 Day 8)
 * 原因:Style Dictionary v4 内部用 dynamic import 加载配置,撞上 CJS 语法。
 * `.mjs` 强制 ESM 后缀,跨 root pnpm / turbo / vitest 加载链路一致。
 *
 * 4 端编译产物:
 *   - dist/css/variables.css        (CSS variables,直接被 admin / app 入口 import)
 *   - dist/element-plus/theme.scss  (Element Plus SCSS map,admin 主题接入 — Day 14-15 完善 adapter)
 *   - dist/tailwind/preset.js       (Tailwind preset,app preset.tailwind.config — Day 14-15 完善 adapter)
 *   - dist/figma/tokens.json        (Figma Tokens 插件 — Day 14-15 加 $type 字段)
 */
export default {
  source: ['tokens/**/*.json'],
  platforms: {
    css: {
      transformGroup: 'css',
      buildPath: 'dist/css/',
      files: [
        {
          destination: 'variables.css',
          format: 'css/variables',
          options: {
            outputReferences: true,
          },
        },
      ],
    },
    'element-plus': {
      transformGroup: 'css',
      buildPath: 'dist/element-plus/',
      files: [
        {
          destination: 'theme.scss',
          format: 'scss/variables',
        },
      ],
    },
    tailwind: {
      transformGroup: 'js',
      buildPath: 'dist/tailwind/',
      files: [
        {
          destination: 'preset.js',
          format: 'javascript/module',
        },
      ],
    },
    figma: {
      transformGroup: 'js',
      buildPath: 'dist/figma/',
      files: [
        {
          destination: 'tokens.json',
          format: 'json/nested',
        },
      ],
    },
  },
};
