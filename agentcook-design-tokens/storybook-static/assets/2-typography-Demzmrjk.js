import{j as n,b as t,C as s}from"./index-mv0wulEZ.js";import{useMDXComponents as l}from"./index-B1KoZos2.js";import{T as o,C as h,F as a,a as d,b as c,L as x}from"./typography.stories-CscYQYYT.js";import"./iframe-V_cqOTcC.js";import"./index-CcqwZOYG.js";import"./_commonjsHelpers-Cpj98o6Y.js";import"./index-Ca4lBP7z.js";import"./index-DrFu-skq.js";function r(i){const e={blockquote:"blockquote",code:"code",h1:"h1",h2:"h2",h3:"h3",hr:"hr",li:"li",p:"p",pre:"pre",strong:"strong",ul:"ul",...l(),...i.components};return n.jsxs(n.Fragment,{children:[n.jsx(t,{of:o}),`
`,n.jsx(e.h1,{id:"typography--字体系统",children:"Typography — 字体系统"}),`
`,n.jsxs(e.blockquote,{children:[`
`,n.jsxs(e.p,{children:["中英文混排是 agentcook 的核心场景(教程读者 90% 中文用户 + 海外破圈预备 10% 英文)。",n.jsx(e.strong,{children:"字体栈、行高、字重的选择必须同时为中英文优化"}),"。"]}),`
`]}),`
`,n.jsx(e.hr,{}),`
`,n.jsx(e.h2,{id:"1-字体栈",children:"1. 字体栈"}),`
`,n.jsx(e.h3,{id:"sans默认正文",children:"sans(默认正文)"}),`
`,n.jsx(e.pre,{children:n.jsx(e.code,{children:`'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif
`})}),`
`,n.jsxs(e.p,{children:[n.jsx(e.strong,{children:"当前问题(Day 6 review T1 红字证据)"}),":",n.jsx(e.strong,{children:"缺中文 fallback"}),"。Inter 不含 CJK,Mac/iOS 靠系统自动 PingFang SC 兜住,Win Chrome 上回退到中易宋(SimSun) — 衬线、字重不齐、视觉灾难。"]}),`
`,n.jsx(s,{of:h}),`
`,n.jsxs(e.p,{children:[n.jsx(e.strong,{children:"Day 14-15 P0-3 修法"}),":加 ",n.jsx(e.code,{children:"'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei'"})," 三档中文 fallback。"]}),`
`,n.jsx(e.h3,{id:"mono代码--等宽",children:"mono(代码 / 等宽)"}),`
`,n.jsx(e.pre,{children:n.jsx(e.code,{children:`'JetBrains Mono', 'Fira Code', monospace
`})}),`
`,n.jsxs(e.p,{children:["同样",n.jsx(e.strong,{children:"缺中文等宽 fallback"}),"(代码块嵌中文注释会跳字)。Day 14-15 加 ",n.jsx(e.code,{children:"'Sarasa Mono SC'"})," 或 ",n.jsx(e.code,{children:"'PingFang SC'"}),"。"]}),`
`,n.jsx(s,{of:a}),`
`,n.jsx(e.hr,{}),`
`,n.jsx(e.h2,{id:"2-字号--8-档",children:"2. 字号 — 8 档"}),`
`,n.jsx(e.pre,{children:n.jsx(e.code,{children:`xs   0.75rem  (12px)   小标 / 时间戳
sm   0.875rem (14px)   表单提示 / 次要文字
base 1rem     (16px)   正文(默认)
lg   1.125rem (18px)   段落强调 / 子标题
xl   1.25rem  (20px)   区块标题
2xl  1.5rem   (24px)   页面 H2
3xl  1.875rem (30px)   页面 H1
4xl  2.25rem  (36px)   landing hero(Phase 3 加 5xl/6xl 更大档)
`})}),`
`,n.jsx(s,{of:d}),`
`,n.jsx(e.hr,{}),`
`,n.jsx(e.h2,{id:"3-字重--4-档",children:"3. 字重 — 4 档"}),`
`,n.jsxs(e.p,{children:[n.jsx(e.code,{children:"normal (400)"})," / ",n.jsx(e.code,{children:"medium (500)"})," / ",n.jsx(e.code,{children:"semibold (600)"})," / ",n.jsx(e.code,{children:"bold (700)"})]}),`
`,n.jsxs(e.p,{children:[n.jsx(e.strong,{children:"双栈使用习惯"}),":"]}),`
`,n.jsxs(e.ul,{children:[`
`,n.jsx(e.li,{children:"admin(Element Plus 紧凑)— 默认 400,标题 600,正文几乎不用 500/700"}),`
`,n.jsx(e.li,{children:"app(shadcn/ui 现代)— 默认 400,标题 600/700,UI 强调用 500"}),`
`]}),`
`,n.jsx(s,{of:c}),`
`,n.jsx(e.hr,{}),`
`,n.jsx(e.h2,{id:"4-行高",children:"4. 行高"}),`
`,n.jsxs(e.p,{children:[n.jsx(e.code,{children:"tight (1.25)"})," / ",n.jsx(e.code,{children:"normal (1.5)"})," / ",n.jsx(e.code,{children:"relaxed (1.75)"})]}),`
`,n.jsxs(e.p,{children:[n.jsx(e.strong,{children:"中英混排准则"}),":"]}),`
`,n.jsxs(e.ul,{children:[`
`,n.jsxs(e.li,{children:[n.jsx(e.strong,{children:"正文"}),":用 ",n.jsx(e.code,{children:"normal"})," (1.5) — 中文字符方块比英文宽 + 高,需要更多行间距才不挤"]}),`
`,n.jsxs(e.li,{children:[n.jsx(e.strong,{children:"标题"}),":用 ",n.jsx(e.code,{children:"tight"})," (1.25) — 标题字号大,过宽行高会让标题显得松散"]}),`
`,n.jsxs(e.li,{children:[n.jsx(e.strong,{children:"大段阅读(blog / docs)"}),":用 ",n.jsx(e.code,{children:"relaxed"})," (1.75)"]}),`
`]}),`
`,n.jsx(s,{of:x}),`
`,n.jsx(e.hr,{}),`
`,n.jsx(e.h2,{id:"5-双栈使用例--同-token-双栈一致",children:"5. 双栈使用例 — 同 token 双栈一致"}),`
`,n.jsx(e.h3,{id:"51-标题层级",children:"5.1 标题层级"}),`
`,n.jsxs("div",{style:{display:"grid",gridTemplateColumns:"1fr 1fr",gap:24,padding:24,background:"#fafafa",borderRadius:8,fontFamily:"'Inter', sans-serif"},children:[n.jsxs("div",{children:[n.jsx("div",{style:{fontSize:12,color:"#737373",marginBottom:12,textTransform:"uppercase",letterSpacing:"0.06em"},children:"admin · 紧凑后台"}),n.jsx("h1",{style:{fontSize:"var(--typography-font-size-2-xl, 1.5rem)",fontWeight:600,lineHeight:"var(--typography-line-height-tight, 1.25)",margin:"0 0 8px"},children:"Plugin 管理"}),n.jsx("p",{style:{fontSize:"var(--typography-font-size-sm, 0.875rem)",color:"#525252",margin:0,lineHeight:"var(--typography-line-height-normal, 1.5)"},children:"共 24 个插件,12 个已启用"})]}),n.jsxs("div",{children:[n.jsx("div",{style:{fontSize:12,color:"#737373",marginBottom:12,textTransform:"uppercase",letterSpacing:"0.06em"},children:"app · 现代消费"}),n.jsx("h1",{style:{fontSize:"var(--typography-font-size-3-xl, 1.875rem)",fontWeight:700,lineHeight:"var(--typography-line-height-tight, 1.25)",margin:"0 0 12px"},children:"Your AI Agents"}),n.jsx("p",{style:{fontSize:"var(--typography-font-size-base, 1rem)",color:"#525252",margin:0,lineHeight:"var(--typography-line-height-relaxed, 1.75)"},children:"Pick a plugin to start a conversation with."})]})]}),`
`,n.jsxs(e.p,{children:[n.jsx(e.strong,{children:"视觉差异"}),":admin 用 2xl + 600(紧凑后台优先信息密度);app 用 3xl + 700(现代消费优先视觉冲击)。",n.jsx(e.strong,{children:"字号 / 字重 token 来自同一份 typography.json"}),"。"]}),`
`,n.jsx(e.h3,{id:"52-chat-消息中英混排",children:"5.2 chat 消息中英混排"}),`
`,n.jsxs("div",{style:{padding:24,background:"#fafafa",borderRadius:8,fontFamily:"'Inter', -apple-system, BlinkMacSystemFont, sans-serif"},children:[n.jsx("div",{style:{fontSize:12,color:"#737373",marginBottom:12,textTransform:"uppercase",letterSpacing:"0.06em"},children:"app · chat 气泡(中英混排)"}),n.jsxs("div",{style:{display:"flex",flexDirection:"column",gap:12,maxWidth:480},children:[n.jsx("div",{style:{alignSelf:"flex-end",background:"#3b82f6",color:"white",padding:"10px 16px",borderRadius:16,fontSize:"var(--typography-font-size-base, 1rem)",lineHeight:"var(--typography-line-height-normal, 1.5)",maxWidth:"80%"},children:n.jsx(e.p,{children:"帮我用 weather-fetcher plugin 查一下 SF 今天天气"})}),n.jsx("div",{style:{alignSelf:"flex-start",background:"white",border:"1px solid #e5e5e5",padding:"10px 16px",borderRadius:16,fontSize:"var(--typography-font-size-base, 1rem)",lineHeight:"var(--typography-line-height-normal, 1.5)",maxWidth:"80%"},children:n.jsxs(e.p,{children:["Calling ",n.jsx("code",{style:{background:"#f5f5f5",padding:"1px 6px",borderRadius:4,fontFamily:"'JetBrains Mono', monospace",fontSize:"0.9em"},children:'weather.get(location: "San Francisco")'})," ...",n.jsx("br",{}),`
旧金山今天 18°C,多云,东南风 8 km/h。建议穿薄外套。`]})})]})]}),`
`,n.jsxs(e.p,{children:[n.jsx(e.strong,{children:"关键"}),":这段渲染",n.jsx(e.strong,{children:"真的暴露了中文 fallback 缺失问题"})," — Mac 用户看着像样(系统兜底 PingFang SC),Win 用户在 Chrome 里看到的中文部分会是中易宋(衬线、笔画细),与 Inter 的英文部分视觉断裂。Day 14-15 修后这个段落会无缝。"]}),`
`,n.jsx(e.hr,{}),`
`,n.jsx(e.h2,{id:"6-给业务代码的写法",children:"6. 给业务代码的写法"}),`
`,n.jsx(e.pre,{children:n.jsx(e.code,{className:"language-jsx",children:`{/* ✅ admin */}
<h1 class="text-2xl font-semibold leading-tight">Plugin 管理</h1>
<p class="text-sm text-neutral-600">共 24 个插件</p>

{/* ✅ app */}
<h1 className="text-3xl font-bold leading-tight">Your AI Agents</h1>
<p className="text-base text-neutral-600 leading-relaxed">Pick a plugin...</p>

{/* ✅ 直接消费 CSS variables(自定义组件)*/}
<h2 style={{
  fontSize: 'var(--typography-font-size-xl)',
  lineHeight: 'var(--typography-line-height-tight)',
  fontWeight: 'var(--typography-font-weight-semibold)',
}}>...</h2>
`})}),`
`,n.jsxs(e.p,{children:[n.jsx(e.strong,{children:"禁止"}),":"]}),`
`,n.jsxs(e.ul,{children:[`
`,n.jsxs(e.li,{children:["在组件里硬编码 ",n.jsx(e.code,{children:"font-size: 14px"})," / ",n.jsx(e.code,{children:"font-weight: 600"})]}),`
`,n.jsxs(e.li,{children:["用 inline ",n.jsx(e.code,{children:"style={{ fontFamily: 'Helvetica' }}"})," 绕过 design tokens"]}),`
`]}),`
`,n.jsx(e.hr,{}),`
`,n.jsx(e.h2,{id:"7-完整-stories",children:"7. 完整 Stories"}),`
`,n.jsxs(e.ul,{children:[`
`,n.jsxs(e.li,{children:[n.jsx(e.strong,{children:"Font Families"})," — sans / mono 字体栈渲染对比"]}),`
`,n.jsxs(e.li,{children:[n.jsx(e.strong,{children:"Font Sizes"})," — 8 档字号"]}),`
`,n.jsxs(e.li,{children:[n.jsx(e.strong,{children:"Font Weights"})," — 4 档字重"]}),`
`,n.jsxs(e.li,{children:[n.jsx(e.strong,{children:"Line Heights"})," — 3 档行高对比"]}),`
`,n.jsxs(e.li,{children:[n.jsx(e.strong,{children:"Chinese Fallback Missing(review evidence)"})," — Day 6 review T1 红字证据"]}),`
`]})]})}function b(i={}){const{wrapper:e}={...l(),...i.components};return e?n.jsx(e,{...i,children:n.jsx(r,{...i})}):r(i)}export{b as default};
