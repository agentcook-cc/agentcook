import{j as n,b as d}from"./index-mv0wulEZ.js";import{useMDXComponents as r}from"./index-B1KoZos2.js";import"./iframe-V_cqOTcC.js";import"./index-CcqwZOYG.js";import"./_commonjsHelpers-Cpj98o6Y.js";import"./index-Ca4lBP7z.js";import"./index-DrFu-skq.js";function i(s){const e={blockquote:"blockquote",code:"code",h1:"h1",h2:"h2",h3:"h3",hr:"hr",li:"li",p:"p",pre:"pre",strong:"strong",ul:"ul",...r(),...s.components};return n.jsxs(n.Fragment,{children:[n.jsx(d,{title:"Foundation/Intro"}),`
`,n.jsx(e.h1,{id:"agentcook-设计系统--设计哲学",children:"agentcook 设计系统 — 设计哲学"}),`
`,n.jsxs(e.blockquote,{children:[`
`,n.jsxs(e.p,{children:['这套设计系统的存在不是为了"看起来很专业",而是为了让 admin(Vue 3 + Element Plus 后台风)和 app(React 19 + Tailwind + shadcn/ui 消费风)在两套截然不同的组件库 / 布局密度 / 用户场景下,',n.jsx(e.strong,{children:"视觉上仍然像同一个产品"}),"。"]}),`
`]}),`
`,n.jsx(e.hr,{}),`
`,n.jsx(e.h2,{id:"四条原则",children:"四条原则"}),`
`,n.jsx(e.h3,{id:"1-双栈一致性优先",children:"1. 双栈一致性优先"}),`
`,n.jsxs(e.p,{children:[n.jsx(e.code,{children:"admin"})," 和 ",n.jsx(e.code,{children:"app"})," 用了完全不同的技术栈,但",n.jsx(e.strong,{children:"以下层面必须零认知差"}),":"]}),`
`,n.jsxs(e.ul,{children:[`
`,n.jsx(e.li,{children:"颜色 / 字体 / 间距(同一 token → 同一像素值)"}),`
`,n.jsx(e.li,{children:"错误码 / 错误文案 / i18n key"}),`
`,n.jsx(e.li,{children:"用户 / 权限模型 / 业务术语"}),`
`,n.jsx(e.li,{children:"API client 类型(从同一份 OpenAPI 生成)"}),`
`]}),`
`,n.jsxs(e.p,{children:["布局密度可以差异化(admin 紧凑后台 / app 现代留白),但",n.jsx(e.strong,{children:"用户从 admin 切到 app"}),",色彩温度、字体观感、按钮形态都要稳定。"]}),`
`,n.jsx(e.h3,{id:"2-单一信源-ssot",children:"2. 单一信源 (SSOT)"}),`
`,n.jsxs(e.p,{children:[`| 共享物 | 唯一信源 | 派生方 |
|--------|---------|--------|
| 设计 token | `,n.jsx(e.code,{children:"tokens/*.json"}),`(本目录) | admin / app / Storybook / Figma |
| API 类型 | OpenAPI v1(后端 Day 24 冻结) | admin / app codegen |
| 错误码 | `,n.jsx(e.code,{children:"agentcook-core/errors.py"}),` | 前端同步生成 enum |
| 业务术语 | glossary.md(Phase 2 加) | i18n / UI / 教程 |`]}),`
`,n.jsxs(e.p,{children:[n.jsx(e.strong,{children:"反例"}),':admin 把 "插件" 翻译成 "扩展",app 翻译成 "插件" — 同一概念双栈不一致 = 失败。']}),`
`,n.jsx(e.h3,{id:"3-反过度抽象",children:"3. 反过度抽象"}),`
`,n.jsxs(e.p,{children:["写第一个 admin 页和第一个 app 页时,",n.jsx(e.strong,{children:"不要"}),"先抽 ",n.jsx(e.code,{children:"useApi"})," / ",n.jsx(e.code,{children:"useAuth"})," / ",n.jsx(e.code,{children:"useFormState"}),' 这种"通用 hook 库"。',n.jsx(e.strong,{children:"三处用到再抽,两处用到就重复"}),"。"]}),`
`,n.jsxs(e.p,{children:["token 也一样:Phase 0 只有 atomic 层(",n.jsx(e.code,{children:"primary.500"})," / ",n.jsx(e.code,{children:"neutral.700"}),"),Phase 1 末才补 semantic 层(",n.jsx(e.code,{children:"text.primary"})," / ",n.jsx(e.code,{children:"bg.surface"})," / ",n.jsx(e.code,{children:"border.default"}),")。",n.jsx(e.strong,{children:"没有真业务消费场景前不做语义抽象"}),"。"]}),`
`,n.jsx(e.h3,{id:"4-atomic--semantic--component-三层",children:"4. Atomic → Semantic → Component 三层"}),`
`,n.jsx(e.pre,{children:n.jsx(e.code,{children:`Component 层    button.primary.bg = ...  ←  组件级 token(等用了真组件再加)
                                  ↓
Semantic 层     text.primary = ...      ←  语义层(Phase 1 末加)
                                  ↓
Atomic 层       primary.500 = #3b82f6   ←  当前(Phase 0 已就位)
`})}),`
`,n.jsxs(e.p,{children:[n.jsx(e.strong,{children:"当前阶段"}),":atomic 完整,semantic 待补,component 不预先建。Phase 3 admin/app 真消费时,反推 semantic / component 层补。"]}),`
`,n.jsx(e.hr,{}),`
`,n.jsx(e.h2,{id:"当前阶段2026-05--phase-1-day-13",children:"当前阶段(2026-05 / Phase 1 Day 13)"}),`
`,n.jsxs(e.p,{children:[`| Token 类 | 状态 | 缺补 |
|----------|------|------|
| `,n.jsx(e.strong,{children:"Color"}),` | atomic 6 色系 + neutral 全档 | primary 缺 200/300/400/800/900;semantic 层未建;dark mode 未建 |
| `,n.jsx(e.strong,{children:"Typography"})," | sans/mono + 8 字号 + 4 字重 + 3 行高 | ",n.jsx(e.strong,{children:"中文 fallback 缺失"}),"(详见 ",n.jsx(e.code,{children:"Foundation > Color > ChineseFallbackMissing"}),`)|
| `,n.jsx(e.strong,{children:"Spacing"}),` | 4px 基线,8 档 | 缺 0/0.5/5/10/20/24,Phase 3 补 |
| `,n.jsx(e.strong,{children:"Radius"}),` | sm/md/lg/full | 缺 xs/xl/2xl(chat 气泡),Phase 3 补 |
| `,n.jsx(e.strong,{children:"Shadow"}),` | sm/md/lg/xl | 缺 inner/focus-ring/dark 变体 |
| `,n.jsx(e.strong,{children:"Motion"})," | 3 时长 + 4 缓动 | ⚠ ",n.jsx(e.code,{children:"easing.inOut"})," 与 ",n.jsx(e.code,{children:"default"})," 数值重复(已知 bug,Day 14-15 修)|"]}),`
`,n.jsxs(e.blockquote,{children:[`
`,n.jsxs(e.p,{children:["完整缺补优先级见 ",n.jsx(e.code,{children:"tutorial/_internal/audit/design-tokens-gaps.md"}),"(P0 8 项 / P1 4 项 / P2 6 项 / P3 6 项)"]}),`
`]}),`
`,n.jsx(e.hr,{}),`
`,n.jsx(e.h2,{id:"双栈消费方式速查",children:"双栈消费方式速查"}),`
`,n.jsxs(e.blockquote,{children:[`
`,n.jsxs(e.p,{children:["完整接入指南见 ",n.jsx(e.code,{children:"frontend-conventions.md"})," §9。"]}),`
`]}),`
`,n.jsx(e.pre,{children:n.jsx(e.code,{className:"language-ts",children:`// admin (Vue 3) - 入口
import '@design-tokens/css/variables.css';
import './styles/element-plus.scss';     // SCSS map 接 Element Plus theme

// app (React 19) - 入口
import '@design-tokens/css/variables.css';
// tailwind.config.js 内:
import preset from '@design-tokens/tailwind/preset.js';
export default { presets: [preset] };
`})}),`
`,n.jsxs(e.p,{children:["业务代码里",n.jsx(e.strong,{children:"不直接写色值 / 字号 / 间距字面量"}),":"]}),`
`,n.jsx(e.pre,{children:n.jsx(e.code,{className:"language-jsx",children:`{/* ❌ */}
<div style={{ color: '#3b82f6', padding: 16 }}>...</div>

{/* ✅ admin */}
<div class="text-primary p-4">...</div>

{/* ✅ app */}
<div className="text-primary-500 p-4">...</div>

{/* ✅ 直接消费 CSS variables(脱离两套样式系统时)*/}
<div style={{ background: 'var(--color-primary-500)', borderRadius: 'var(--radius-md)' }}>...</div>
`})}),`
`,n.jsx(e.hr,{}),`
`,n.jsx(e.h2,{id:"导航",children:"导航"}),`
`,n.jsxs(e.ul,{children:[`
`,n.jsxs(e.li,{children:[n.jsx(e.strong,{children:"Foundation/Color"}),"(这一组)— 6 色系 atomic + Primary Gap 评审证据 + 双栈 Button 并排"]}),`
`,n.jsxs(e.li,{children:[n.jsx(e.strong,{children:"Foundation/Typography"})," — 字体栈 / 字号 / 字重 + ",n.jsx(e.strong,{children:"Chinese Fallback Missing 评审证据"})]}),`
`,n.jsxs(e.li,{children:[n.jsx(e.strong,{children:"Foundation/Spacing"})," — 4px 基线 + 真实卡片层级 demo + 双栈 padding 风格对比"]}),`
`,n.jsxs(e.li,{children:[n.jsx(e.strong,{children:"Foundation/Radius"})," — 4 档圆角(待补 chat 气泡用 2xl)"]}),`
`,n.jsxs(e.li,{children:[n.jsx(e.strong,{children:"Foundation/Shadow"})," — 4 档阴影分层"]}),`
`,n.jsxs(e.li,{children:[n.jsx(e.strong,{children:"Foundation/Motion"})," — 3 时长 + 4 缓动 + ⚠ inOut bug 红字"]}),`
`]}),`
`,n.jsx(e.hr,{}),`
`,n.jsx(e.h2,{id:"给作者--reviewer",children:"给作者 / Reviewer"}),`
`,n.jsxs(e.p,{children:['打开 Storybook 看到的不是"漂亮的色卡"。这是 ',n.jsx(e.strong,{children:"Phase 0 助手 F 的产出 + Phase 1 Agent B 的接手 review"}),' 共同呈现的"半成品现场":合理的部分作为基线,缺的部分用 ',n.jsx(e.code,{children:"Primary Gap"})," / ",n.jsx(e.code,{children:"Chinese Fallback Missing"})," 等 ",n.jsx(e.strong,{children:"review evidence story"})," 显式硬显,",n.jsx(e.strong,{children:'让所有跨 Agent 协作的人(A / C / D)都能看到一份不撒谎的 "this is where we are now"'}),"。"]}),`
`,n.jsx(e.p,{children:'按 v4.2 真实性红线 — 不画"理想态"的设计稿,只展示 token 实际存在的状态 + 实际缺的部分。'})]})}function j(s={}){const{wrapper:e}={...r(),...s.components};return e?n.jsx(e,{...s,children:n.jsx(i,{...s})}):i(s)}export{j as default};
