import{j as e,b as a,C as s}from"./index-mv0wulEZ.js";import{useMDXComponents as o}from"./index-B1KoZos2.js";import{C as d,P as t,a as l}from"./colors.stories-DOL74Yz6.js";import"./iframe-V_cqOTcC.js";import"./index-CcqwZOYG.js";import"./_commonjsHelpers-Cpj98o6Y.js";import"./index-Ca4lBP7z.js";import"./index-DrFu-skq.js";function i(n){const r={blockquote:"blockquote",code:"code",h1:"h1",h2:"h2",h3:"h3",hr:"hr",li:"li",p:"p",pre:"pre",strong:"strong",ul:"ul",...o(),...n.components};return e.jsxs(e.Fragment,{children:[e.jsx(a,{of:d}),`
`,e.jsx(r.h1,{id:"color--色彩系统",children:"Color — 色彩系统"}),`
`,e.jsxs(r.blockquote,{children:[`
`,e.jsxs(r.p,{children:["6 色系 atomic 层 + neutral 全色阶。",e.jsx(r.code,{children:"admin"}),"(Element Plus)与 ",e.jsx(r.code,{children:"app"}),"(Tailwind)双栈共享同一份色值。Phase 1 末补 semantic 层(",e.jsx(r.code,{children:"text.primary"})," / ",e.jsx(r.code,{children:"bg.surface"})," 等),Phase 2 加 dark mode 集。"]}),`
`]}),`
`,e.jsx(r.hr,{}),`
`,e.jsx(r.h2,{id:"1-当前色彩结构",children:"1. 当前色彩结构"}),`
`,e.jsx(r.pre,{children:e.jsx(r.code,{children:`color
├── primary    (50/100/500/600/700)        ← 缺 200/300/400/800/900,Day 14-15 P0-1
├── secondary  (50/500/600)                ← 太薄,Phase 1 末补
├── success    (50/500/600)                ← 同上
├── warning    (50/500/600)                ← 同上
├── danger     (50/500/600)                ← 同上
└── neutral    (50/100/200/300/400/500/600/700/800/900)  ← 完整 10 档
`})}),`
`,e.jsx(r.p,{children:"完整色板:"}),`
`,e.jsx(s,{of:t}),`
`,e.jsx(r.hr,{}),`
`,e.jsx(r.h2,{id:"2--primary-缺中间色阶day-6-review-c1-红字证据",children:"2. ⚠ Primary 缺中间色阶(Day 6 review C1 红字证据)"}),`
`,e.jsx(s,{of:l}),`
`,e.jsxs(r.p,{children:[e.jsx(r.strong,{children:"为什么这是大问题"}),":Element Plus / shadcn/ui 表单聚焦态、按钮 hover/disabled、prose ",e.jsx(r.code,{children:"<a>"})," 链接 visited 态都要中间色阶过渡。当前只有 5 档,做一次 hover 渐变都不连续。Day 14-15 P0-1 补全到 10 档(对齐 neutral 规模)。"]}),`
`,e.jsx(r.hr,{}),`
`,e.jsx(r.h2,{id:"3-双栈使用例--同-token-双栈一致",children:"3. 双栈使用例 — 同 token 双栈一致"}),`
`,e.jsxs(r.p,{children:["下面三组样例展示",e.jsxs(r.strong,{children:["同一份 ",e.jsx(r.code,{children:"--color-primary-500"})," token 在两套样式系统下渲染出像素级一致的视觉"]}),":"]}),`
`,e.jsx(r.h3,{id:"31-默认-button主品牌色",children:"3.1 默认 Button(主品牌色)"}),`
`,e.jsxs("div",{style:{display:"grid",gridTemplateColumns:"1fr 1fr",gap:24,padding:24,background:"#fafafa",borderRadius:8},children:[e.jsxs("div",{children:[e.jsx("div",{style:{fontSize:12,color:"#737373",marginBottom:8,textTransform:"uppercase",letterSpacing:"0.06em"},children:"admin · Element Plus"}),e.jsx("button",{style:{background:"var(--color-primary-500, #3b82f6)",color:"white",border:"none",padding:"8px 16px",borderRadius:"var(--radius-sm, 4px)",fontSize:14,cursor:"pointer",fontFamily:"'Inter', sans-serif"},children:"提交"})]}),e.jsxs("div",{children:[e.jsx("div",{style:{fontSize:12,color:"#737373",marginBottom:8,textTransform:"uppercase",letterSpacing:"0.06em"},children:"app · Tailwind + shadcn/ui"}),e.jsx("button",{style:{background:"var(--color-primary-500, #3b82f6)",color:"white",border:"none",padding:"10px 16px",borderRadius:"var(--radius-md, 8px)",fontSize:14,fontWeight:500,cursor:"pointer",fontFamily:"'Inter', sans-serif"},children:"Submit"})]})]}),`
`,e.jsxs(r.p,{children:[e.jsx(r.strong,{children:"视觉差异"}),":admin 紧凑(8/4 padding + sm radius)/ app 现代(10/8 padding + md radius)。",e.jsx(r.strong,{children:"色值像素一致"}),"(同一 ",e.jsx(r.code,{children:"--color-primary-500"}),")。"]}),`
`,e.jsx(r.pre,{children:e.jsx(r.code,{className:"language-ts",children:`// admin/styles/element-plus.scss(Day 14-15 SD adapter 完善后)
@use '@design-tokens/element-plus/theme.scss' as tokens;
@use 'element-plus/theme-chalk/src/index.scss' as * with (
  $colors: ('primary': ('base': tokens.$color-primary-500)),
);

// app/tailwind.config.js
import preset from '@design-tokens/tailwind/preset.js';
export default { presets: [preset], content: [...] };
// 然后用 className="bg-primary-500 text-white"
`})}),`
`,e.jsx(r.h3,{id:"32-danger-button删除--危险动作",children:"3.2 Danger Button(删除 / 危险动作)"}),`
`,e.jsxs("div",{style:{display:"grid",gridTemplateColumns:"1fr 1fr",gap:24,padding:24,background:"#fafafa",borderRadius:8},children:[e.jsxs("div",{children:[e.jsx("div",{style:{fontSize:12,color:"#737373",marginBottom:8,textTransform:"uppercase",letterSpacing:"0.06em"},children:"admin · Element Plus"}),e.jsx("button",{style:{background:"var(--color-danger-500, #ef4444)",color:"white",border:"none",padding:"8px 16px",borderRadius:"var(--radius-sm, 4px)",fontSize:14,cursor:"pointer",fontFamily:"'Inter', sans-serif"},children:"删除 Plugin"})]}),e.jsxs("div",{children:[e.jsx("div",{style:{fontSize:12,color:"#737373",marginBottom:8,textTransform:"uppercase",letterSpacing:"0.06em"},children:"app · Tailwind + shadcn/ui"}),e.jsx("button",{style:{background:"var(--color-danger-500, #ef4444)",color:"white",border:"none",padding:"10px 16px",borderRadius:"var(--radius-md, 8px)",fontSize:14,fontWeight:500,cursor:"pointer",fontFamily:"'Inter', sans-serif"},children:"Delete Session"})]})]}),`
`,e.jsx(r.h3,{id:"33-tag--badge状态标记",children:"3.3 Tag / Badge(状态标记)"}),`
`,e.jsxs("div",{style:{display:"grid",gridTemplateColumns:"1fr 1fr",gap:24,padding:24,background:"#fafafa",borderRadius:8},children:[e.jsxs("div",{children:[e.jsx("div",{style:{fontSize:12,color:"#737373",marginBottom:8,textTransform:"uppercase",letterSpacing:"0.06em"},children:"admin · 紧凑标签"}),e.jsxs("div",{style:{display:"flex",gap:8},children:[e.jsx("span",{style:{padding:"2px 8px",background:"var(--color-success-50, #f0fdf4)",color:"var(--color-success-600, #16a34a)",borderRadius:4,fontSize:12,fontFamily:"'Inter', sans-serif"},children:"已启用"}),e.jsx("span",{style:{padding:"2px 8px",background:"var(--color-warning-50, #fffbeb)",color:"var(--color-warning-600, #d97706)",borderRadius:4,fontSize:12,fontFamily:"'Inter', sans-serif"},children:"待审核"}),e.jsx("span",{style:{padding:"2px 8px",background:"var(--color-danger-50, #fef2f2)",color:"var(--color-danger-600, #dc2626)",borderRadius:4,fontSize:12,fontFamily:"'Inter', sans-serif"},children:"已禁用"})]})]}),e.jsxs("div",{children:[e.jsx("div",{style:{fontSize:12,color:"#737373",marginBottom:8,textTransform:"uppercase",letterSpacing:"0.06em"},children:"app · 现代留白标签"}),e.jsxs("div",{style:{display:"flex",gap:8},children:[e.jsx("span",{style:{padding:"4px 10px",background:"var(--color-success-50, #f0fdf4)",color:"var(--color-success-600, #16a34a)",borderRadius:999,fontSize:12,fontWeight:500,fontFamily:"'Inter', sans-serif"},children:"active"}),e.jsx("span",{style:{padding:"4px 10px",background:"var(--color-warning-50, #fffbeb)",color:"var(--color-warning-600, #d97706)",borderRadius:999,fontSize:12,fontWeight:500,fontFamily:"'Inter', sans-serif"},children:"pending"}),e.jsx("span",{style:{padding:"4px 10px",background:"var(--color-danger-50, #fef2f2)",color:"var(--color-danger-600, #dc2626)",borderRadius:999,fontSize:12,fontWeight:500,fontFamily:"'Inter', sans-serif"},children:"disabled"})]})]})]}),`
`,e.jsx(r.hr,{}),`
`,e.jsx(r.h2,{id:"4-当前展示用-html-模拟phase-3-起切真组件",children:"4. 当前展示用 HTML 模拟,Phase 3 起切真组件"}),`
`,e.jsxs(r.blockquote,{children:[`
`,e.jsxs(r.p,{children:['⚠ 本页所有"双栈并排"展示',e.jsx(r.strong,{children:"当前用 HTML + CSS variables 模拟"})," Element Plus / shadcn 视觉效果。等 Phase 3 Day 26+ admin/app 真 src 落地、Vue/React 组件 stories 出来后,会换成真 ",e.jsx(r.code,{children:"<el-button>"})," / ",e.jsx(r.code,{children:"<Button>"})," 双栈渲染(用 Storybook html-vite render() 函数 mount)。"]}),`
`]}),`
`,e.jsx(r.hr,{}),`
`,e.jsx(r.h2,{id:"5-即将到来--semantic-层phase-1-末",children:"5. 即将到来 — Semantic 层(Phase 1 末)"}),`
`,e.jsxs(r.p,{children:["Day 14-15 后会引入 ",e.jsx(r.code,{children:"tokens/color.semantic.json"}),",业务消费方应优先用 semantic 层:"]}),`
`,e.jsx(r.pre,{children:e.jsx(r.code,{className:"language-jsonc",children:`// 引入后(Phase 1 末)
{
  "color": {
    "text":   { "primary": "{color.neutral.900}", "secondary": "{color.neutral.600}", "muted": "{color.neutral.400}" },
    "bg":     { "canvas": "{color.neutral.50}", "surface": "#ffffff", "elevated": "#ffffff" },
    "border": { "default": "{color.neutral.200}", "subtle": "{color.neutral.100}", "focus": "{color.primary.500}" }
  }
}
`})}),`
`,e.jsx(r.p,{children:"业务代码改用:"}),`
`,e.jsx(r.pre,{children:e.jsx(r.code,{className:"language-jsx",children:`{/* 引入 semantic 后,这才是默认推荐写法 */}
<div style={{ color: 'var(--color-text-primary)', background: 'var(--color-bg-surface)' }}>...</div>
`})}),`
`,e.jsxs(r.p,{children:[e.jsx(r.strong,{children:"为什么"}),":换品牌色 / 切 dark mode 只改 semantic 映射,业务代码不动。",e.jsx(r.code,{children:"primary.500"})," 这种 atomic 引用应",e.jsx(r.strong,{children:"只出现在 semantic 定义和 design system 内部"}),",不出现在业务组件里。"]}),`
`,e.jsx(r.hr,{}),`
`,e.jsx(r.h2,{id:"6-完整-stories",children:"6. 完整 Stories"}),`
`,e.jsx(r.p,{children:"下方所有 stories 在左侧 sidebar 可单独打开:"}),`
`,e.jsxs(r.ul,{children:[`
`,e.jsxs(r.li,{children:[e.jsx(r.strong,{children:"Palette"})," — 全色板 6 色系 + neutral 完整渲染"]}),`
`,e.jsxs(r.li,{children:[e.jsx(r.strong,{children:"Primary Gap (review evidence)"})," — Day 6 review C1 红字证据"]}),`
`]})]})}function j(n={}){const{wrapper:r}={...o(),...n.components};return r?e.jsx(r,{...n,children:e.jsx(i,{...n})}):i(n)}export{j as default};
