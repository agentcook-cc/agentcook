import{j as n,b as r}from"./index-mv0wulEZ.js";import{useMDXComponents as o}from"./index-B1KoZos2.js";import"./iframe-V_cqOTcC.js";import"./index-CcqwZOYG.js";import"./_commonjsHelpers-Cpj98o6Y.js";import"./index-Ca4lBP7z.js";import"./index-DrFu-skq.js";function s(i){const e={blockquote:"blockquote",code:"code",h1:"h1",h2:"h2",li:"li",ol:"ol",p:"p",strong:"strong",ul:"ul",...o(),...i.components};return n.jsxs(n.Fragment,{children:[n.jsx(r,{title:"Welcome"}),`
`,n.jsx(e.h1,{id:"agentcook-design-tokens",children:"agentcook Design Tokens"}),`
`,n.jsxs(e.blockquote,{children:[`
`,n.jsxs(e.p,{children:["共享设计系统的单一信源。",n.jsx(e.code,{children:"admin"}),"(Vue 3 + Element Plus)与 ",n.jsx(e.code,{children:"app"}),"(React + Tailwind + shadcn/ui)双栈消费同一份 token,视觉一致性由此保证。"]}),`
`]}),`
`,n.jsx(e.h2,{id:"当前状态2026-05-17--phase-1-day-7",children:"当前状态(2026-05-17 / Phase 1 Day 7)"}),`
`,n.jsxs(e.ul,{children:[`
`,n.jsx(e.li,{children:"✅ 6 类 token JSON(color / typography / spacing / radius / shadow / motion)就位"}),`
`,n.jsx(e.li,{children:"✅ Style Dictionary 4 端编译配置(CSS variables / Element Plus theme / Tailwind preset / Figma)"}),`
`,n.jsx(e.li,{children:"✅ Storybook 8 + html-vite 双栈展示框架(本页所在)"}),`
`,n.jsx(e.li,{children:"🚧 token 缺补(primary 中间色阶 / semantic 语义层 / dark mode / 中文字体 fallback)— Day 14-15 / Phase 2 Day 22-23 分批补"}),`
`,n.jsx(e.li,{children:"🚧 Vue / React 组件 stories(Day 8 加 Element Plus Button + shadcn/ui Button 并排展示)"}),`
`]}),`
`,n.jsx(e.h2,{id:"导航",children:"导航"}),`
`,n.jsxs(e.ul,{children:[`
`,n.jsxs(e.li,{children:[n.jsx(e.strong,{children:"Foundation/Colors"})," — 6 色系(primary / secondary / success / warning / danger / neutral)"]}),`
`,n.jsxs(e.li,{children:[n.jsx(e.strong,{children:"Foundation/Typography"})," — 字体栈 / 字号 / 行高 / 字重"]}),`
`,n.jsxs(e.li,{children:[n.jsx(e.strong,{children:"Foundation/Spacing"})," — 4px 基线间距系统"]}),`
`,n.jsxs(e.li,{children:[n.jsx(e.strong,{children:"Foundation/Radius"})," — 圆角档位"]}),`
`,n.jsxs(e.li,{children:[n.jsx(e.strong,{children:"Foundation/Shadow"})," — 阴影分层"]}),`
`,n.jsxs(e.li,{children:[n.jsx(e.strong,{children:"Foundation/Motion"})," — 动效时长 + 缓动曲线"]}),`
`]}),`
`,n.jsx(e.h2,{id:"原则",children:"原则"}),`
`,n.jsxs(e.ol,{children:[`
`,n.jsxs(e.li,{children:[n.jsx(e.strong,{children:"Atomic → Semantic → Component"})," 三层 — 当前只有 atomic,Phase 1 末补完 semantic"]}),`
`,n.jsxs(e.li,{children:[n.jsx(e.strong,{children:"单一信源"})," — 任何色值改动只在 ",n.jsx(e.code,{children:"tokens/*.json"}),",SD 编译同步到 4 端"]}),`
`,n.jsxs(e.li,{children:[n.jsx(e.strong,{children:"双栈一致"})," — admin 紧凑布局 + app 现代留白,但同 token 出同色值"]}),`
`,n.jsxs(e.li,{children:[n.jsx(e.strong,{children:"dark mode is a token concern, not a CSS hack"})," — Phase 2 Day 22-23 引入 dark token 集"]}),`
`]}),`
`,n.jsx(e.h2,{id:"参考决策",children:"参考决策"}),`
`,n.jsxs(e.ul,{children:[`
`,n.jsxs(e.li,{children:["ADR-003(",n.jsx(e.code,{children:"tutorial/_internal/L3-strategy/v6-architecture-rationale.md"}),")"]}),`
`]})]})}function j(i={}){const{wrapper:e}={...o(),...i.components};return e?n.jsx(e,{...i,children:n.jsx(s,{...i})}):s(i)}export{j as default};
