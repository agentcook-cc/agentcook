import { defineConfig } from "vitepress";

/**
 * agentcook.cc — public documentation site
 *
 * Deploys to Cloudflare Pages → CNAME agentcook.cc.
 * Build: `pnpm --filter @agentcook-cc/docs-site docs:build`
 * Output: `docs-site/.vitepress/dist`
 *
 * Sidebar mirrors the on-disk structure under `docs-site/`.
 */
export default defineConfig({
  title: "agentcook",
  description: "Production-grade AI agent framework — Python + Java + TypeScript",
  lang: "zh-CN",
  cleanUrls: true,
  lastUpdated: true,
  ignoreDeadLinks: true,
  head: [
    ["link", { rel: "icon", href: "/favicon.svg", type: "image/svg+xml" }],
    ["meta", { name: "theme-color", content: "#3b82f6" }],
  ],
  themeConfig: {
    logo: "/logo.svg",
    nav: [
      { text: "指南", link: "/guide/installation" },
      { text: "API 参考", link: "/reference/python-sdk" },
      { text: "ADR", link: "/adr/" },
      {
        text: "v1.0",
        items: [
          { text: "Changelog", link: "https://github.com/agentcook-cc/agentcook/releases" },
          { text: "GitHub", link: "https://github.com/agentcook-cc/agentcook" },
        ],
      },
    ],
    sidebar: {
      "/guide/": [
        {
          text: "Getting Started",
          items: [
            { text: "Installation", link: "/guide/installation" },
            { text: "Quickstart", link: "/guide/quickstart" },
            { text: "Your First Plugin", link: "/guide/first-plugin" },
          ],
        },
      ],
      "/reference/": [
        {
          text: "API Reference",
          items: [
            { text: "Python SDK", link: "/reference/python-sdk" },
            { text: "Java REST", link: "/reference/java-rest" },
            { text: "gRPC", link: "/reference/grpc" },
          ],
        },
      ],
      "/adr/": [
        {
          text: "Architecture Decision Records",
          items: [{ text: "Index", link: "/adr/" }],
        },
      ],
    },
    socialLinks: [
      { icon: "github", link: "https://github.com/agentcook-cc/agentcook" },
    ],
    footer: {
      message: "Released under the Apache 2.0 License.",
      copyright: "Copyright © 2026 agentcook",
    },
    search: { provider: "local" },
    editLink: {
      pattern: "https://github.com/agentcook-cc/agentcook/edit/main/docs-site/:path",
      text: "Edit this page on GitHub",
    },
    outline: { level: [2, 3] },
  },
});
