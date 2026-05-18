import{j as n,b as a,C as d}from"./index-mv0wulEZ.js";import{useMDXComponents as l}from"./index-B1KoZos2.js";import{S as c,R as o,a as x}from"./spacing.stories-kAuwMBSD.js";import"./iframe-V_cqOTcC.js";import"./index-CcqwZOYG.js";import"./_commonjsHelpers-Cpj98o6Y.js";import"./index-Ca4lBP7z.js";import"./index-DrFu-skq.js";function r(e){const i={blockquote:"blockquote",code:"code",div:"div",h1:"h1",h2:"h2",h3:"h3",hr:"hr",input:"input",label:"label",li:"li",ol:"ol",p:"p",pre:"pre",span:"span",strong:"strong",ul:"ul",...l(),...e.components};return n.jsxs(n.Fragment,{children:[n.jsx(a,{of:c}),`
`,n.jsx(i.h1,{id:"spacing--4px-基线--8pt-网格",children:"Spacing — 4px 基线 / 8pt 网格"}),`
`,n.jsxs(i.blockquote,{children:[`
`,n.jsxs(i.p,{children:["所有间距值是 ",n.jsx(i.strong,{children:"4px 的整数倍"}),"。这个约束让双栈 UI 在视觉节奏上锁齐 — admin 紧凑布局 / app 现代留白可以选不同档位,但",n.jsx(i.strong,{children:"同档位下的像素值绝对一致"}),"。"]}),`
`]}),`
`,n.jsx(i.hr,{}),`
`,n.jsx(i.h2,{id:"1-为什么-4px-基线",children:"1. 为什么 4px 基线"}),`
`,n.jsxs(i.p,{children:["业界主流做法(Material Design / Tailwind / Carbon)。",n.jsx(i.strong,{children:"理由"}),":"]}),`
`,n.jsxs(i.ol,{children:[`
`,n.jsx(i.li,{children:"大多数 UI 控件的最小可点区域是 32px(iOS HIG)/ 48px(Material AA),都是 4 的倍数 — 4px 基线天然兼容"}),`
`,n.jsx(i.li,{children:"retina 屏(2x DPR)下 4px = 8 物理像素,边缘不糊"}),`
`,n.jsx(i.li,{children:"设计师 / 工程师 / 截图工具的基本 grid snap 单位都是 4 / 8"}),`
`]}),`
`,n.jsxs(i.p,{children:[n.jsx(i.strong,{children:"8pt 网格"}),' 是 4px 基线的"双倍同步"变体:',n.jsx(i.strong,{children:"主要间距用 8 的倍数"}),"(8/16/24/32),零碎调整用 4(spacing-1)。我们的 token 用数字命名(",n.jsx(i.code,{children:"1"})," / ",n.jsx(i.code,{children:"2"})," / ",n.jsx(i.code,{children:"3"})," / ",n.jsx(i.code,{children:"4"})," ...)正好对应 4px 倍数。"]}),`
`,n.jsx(i.hr,{}),`
`,n.jsx(i.h2,{id:"2-当前-8-档",children:"2. 当前 8 档"}),`
`,n.jsx(i.pre,{children:n.jsx(i.code,{children:`spacing-1   4px      微调 / icon padding
spacing-2   8px      表单元素垂直间距
spacing-3   12px     按钮 padding
spacing-4   16px     正文段落间距 / 卡片 padding
spacing-6   24px     卡片之间 / section 间距
spacing-8   32px     页面块状区分
spacing-12  48px     大区块 / hero 上下
spacing-16  64px     首屏 hero / landing 巨型间距
`})}),`
`,n.jsxs(i.p,{children:[n.jsx(i.strong,{children:"缺补预告"}),"(Phase 3 按需加):"]}),`
`,n.jsxs(i.ul,{children:[`
`,n.jsxs(i.li,{children:[n.jsx(i.code,{children:"0"})," (0px) / ",n.jsx(i.code,{children:"0.5"})," (2px) — 极致微调"]}),`
`,n.jsxs(i.li,{children:[n.jsx(i.code,{children:"5"})," (20px) / ",n.jsx(i.code,{children:"10"})," (40px) — 8/12 / 12/16 之间的中间档"]}),`
`,n.jsxs(i.li,{children:[n.jsx(i.code,{children:"20"})," (80px) / ",n.jsx(i.code,{children:"24"})," (96px) / ",n.jsx(i.code,{children:"32"})," (128px) — landing 页大间距"]}),`
`]}),`
`,n.jsx(d,{of:o}),`
`,n.jsx(i.hr,{}),`
`,n.jsx(i.h2,{id:"3-真实卡片层级-demo",children:"3. 真实卡片层级 demo"}),`
`,n.jsx(i.p,{children:"把 spacing-1 / 2 / 4 / 6 用在一张真实 Plugin 卡片里,层级关系一目了然:"}),`
`,n.jsx(d,{of:x}),`
`,n.jsxs(i.p,{children:[n.jsx(i.strong,{children:"层级解析"}),":"]}),`
`,n.jsxs(i.ul,{children:[`
`,n.jsxs(i.li,{children:[n.jsx(i.code,{children:"padding: spacing-6"})," (24px) — 卡片整体内边距,呼吸感"]}),`
`,n.jsxs(i.li,{children:[n.jsx(i.code,{children:"margin-bottom: spacing-2"})," (8px) — 标题 → 描述"]}),`
`,n.jsxs(i.li,{children:[n.jsx(i.code,{children:"margin-bottom: spacing-4"})," (16px) — 描述 → 标签区"]}),`
`,n.jsxs(i.li,{children:[n.jsx(i.code,{children:"gap: spacing-2"})," (8px) — 标签之间"]}),`
`,n.jsxs(i.li,{children:[n.jsx(i.code,{children:"padding: spacing-1 spacing-2"})," (4px / 8px) — 标签内边距"]}),`
`]}),`
`,n.jsxs(i.p,{children:[n.jsx(i.strong,{children:"禁忌"}),":同一组件内乱用零碎 5/7/13/19px 这种非 4 倍数。视觉上看不出差,但累积起来 grid 就乱了。"]}),`
`,n.jsx(i.hr,{}),`
`,n.jsx(i.h2,{id:"4-双栈使用例--admin-紧凑-vs-app-现代",children:"4. 双栈使用例 — admin 紧凑 vs app 现代"}),`
`,n.jsx(i.h3,{id:"41-列表项密度",children:"4.1 列表项密度"}),`
`,n.jsxs("div",{style:{display:"grid",gridTemplateColumns:"1fr 1fr",gap:24,padding:24,background:"#fafafa",borderRadius:8,fontFamily:"'Inter', sans-serif"},children:[n.jsxs("div",{children:[n.jsx("div",{style:{fontSize:12,color:"#737373",marginBottom:12,textTransform:"uppercase",letterSpacing:"0.06em"},children:"admin · 紧凑(信息密度优先)"}),n.jsx("div",{style:{background:"white",border:"1px solid #e5e5e5",borderRadius:4,overflow:"hidden"},children:["weather-fetcher","github-integration","jira-sync","slack-notifier"].map((s,p)=>n.jsxs(i.div,{style:{padding:"var(--spacing-2, 8px) var(--spacing-4, 16px)",borderTop:p===0?"none":"1px solid #f5f5f5",fontSize:14,display:"flex",justifyContent:"space-between",alignItems:"center"},children:[n.jsx(i.span,{children:s}),n.jsx(i.span,{style:{color:"#22c55e",fontSize:12},children:"● 已启用"})]},s))}),n.jsx("p",{style:{fontSize:11,color:"#737373",marginTop:8,fontFamily:"'JetBrains Mono', monospace"},children:"row padding: spacing-2 / 4 (8px / 16px)"})]}),n.jsxs("div",{children:[n.jsx("div",{style:{fontSize:12,color:"#737373",marginBottom:12,textTransform:"uppercase",letterSpacing:"0.06em"},children:"app · 现代(留白优先)"}),n.jsx("div",{style:{display:"flex",flexDirection:"column",gap:"var(--spacing-3, 12px)"},children:["weather-fetcher","github-integration","jira-sync","slack-notifier"].map(s=>n.jsxs(i.div,{style:{padding:"var(--spacing-4, 16px) var(--spacing-6, 24px)",background:"white",border:"1px solid #e5e5e5",borderRadius:12,fontSize:15,display:"flex",justifyContent:"space-between",alignItems:"center"},children:[n.jsx(i.span,{style:{fontWeight:500},children:s}),n.jsx(i.span,{style:{background:"#f0fdf4",color:"#16a34a",fontSize:12,padding:"4px 10px",borderRadius:999,fontWeight:500},children:"active"})]},s))}),n.jsx("p",{style:{fontSize:11,color:"#737373",marginTop:8,fontFamily:"'JetBrains Mono', monospace"},children:"card padding: spacing-4 / 6 (16px / 24px), card gap: spacing-3 (12px)"})]})]}),`
`,n.jsxs(i.p,{children:[n.jsx(i.strong,{children:"关键观察"}),":同样 4 个 Plugin,admin 占 ~150px 高度(紧凑表格),app 占 ~280px 高度(独立卡片)。",n.jsx(i.strong,{children:"两者用的都是 design-tokens 的 spacing 档位,只是组合策略不同"}),'。哪种风格"更好"取决于场景:']}),`
`,n.jsxs(i.ul,{children:[`
`,n.jsx(i.li,{children:"admin 的运营 / 配置类高频操作 → 紧凑表格更高效"}),`
`,n.jsx(i.li,{children:"app 的用户消费 / 浏览类场景 → 卡片留白更舒适"}),`
`]}),`
`,n.jsxs(i.p,{children:[n.jsx(i.strong,{children:"禁止"}),":不允许任何一边写 ",n.jsx(i.code,{children:"padding: 7px"})," / ",n.jsx(i.code,{children:"padding: 13px"})," 这种偏离 4 倍数的值。如果发现某档不够用(比如想要 20px) → 加 ",n.jsx(i.code,{children:"spacing-5"})," token,不在组件内硬编码。"]}),`
`,n.jsx(i.h3,{id:"42-表单字段间距",children:"4.2 表单字段间距"}),`
`,n.jsxs("div",{style:{display:"grid",gridTemplateColumns:"1fr 1fr",gap:24,padding:24,background:"#fafafa",borderRadius:8,fontFamily:"'Inter', sans-serif"},children:[n.jsxs("div",{children:[n.jsx("div",{style:{fontSize:12,color:"#737373",marginBottom:12,textTransform:"uppercase",letterSpacing:"0.06em"},children:"admin · 表单(field gap: spacing-3)"}),n.jsx("div",{style:{display:"flex",flexDirection:"column",gap:"var(--spacing-3, 12px)"},children:["用户名","邮箱","密码"].map(s=>n.jsxs(i.label,{style:{display:"flex",flexDirection:"column",gap:"var(--spacing-1, 4px)",fontSize:13},children:[n.jsx(i.span,{style:{color:"#525252"},children:s}),n.jsx(i.input,{style:{padding:"6px 10px",border:"1px solid #d4d4d4",borderRadius:4,fontSize:14}})]},s))})]}),n.jsxs("div",{children:[n.jsx("div",{style:{fontSize:12,color:"#737373",marginBottom:12,textTransform:"uppercase",letterSpacing:"0.06em"},children:"app · 表单(field gap: spacing-4)"}),n.jsx("div",{style:{display:"flex",flexDirection:"column",gap:"var(--spacing-4, 16px)"},children:["Email","Password","Confirm Password"].map(s=>n.jsxs(i.label,{style:{display:"flex",flexDirection:"column",gap:"var(--spacing-2, 8px)",fontSize:14},children:[n.jsx(i.span,{style:{color:"#525252",fontWeight:500},children:s}),n.jsx(i.input,{style:{padding:"10px 14px",border:"1px solid #d4d4d4",borderRadius:8,fontSize:14}})]},s))})]})]}),`
`,n.jsxs(i.p,{children:[n.jsx(i.strong,{children:"双栈节奏对照表"}),":"]}),`
`,n.jsx(i.p,{children:`| 用途 | admin 档位 | app 档位 | 比例 |
|------|-----------|---------|------|
| label → input | spacing-1 (4px) | spacing-2 (8px) | 1:2 |
| field → field | spacing-3 (12px) | spacing-4 (16px) | 1:1.33 |
| section gap | spacing-6 (24px) | spacing-8 (32px) | 1:1.33 |`}),`
`,n.jsxs(i.p,{children:[n.jsx(i.strong,{children:"经验法则"}),':app 比 admin 留白多 1 档(spacing-N → spacing-N+1)。这是双栈密度差异的"系数",不是随便选的。']}),`
`,n.jsx(i.hr,{}),`
`,n.jsx(i.h2,{id:"5-给业务代码的写法",children:"5. 给业务代码的写法"}),`
`,n.jsx(i.pre,{children:n.jsx(i.code,{className:"language-jsx",children:`{/* ✅ admin Tailwind class(配 design-tokens preset 后,4 = 16px 一致)*/}
<div class="p-4 mb-2">...</div>

{/* ✅ app Tailwind class */}
<div className="p-6 gap-4">...</div>

{/* ✅ CSS variables(自定义组件 / SCSS / 非 Tailwind 场景)*/}
<div style={{ padding: 'var(--spacing-4)', marginBottom: 'var(--spacing-2)' }}>...</div>

{/* ❌ 反例 */}
<div style={{ padding: 17, marginBottom: 9 }}>...</div>      {/* 偏离 4 倍数 */}
<div style={{ padding: '0.875rem 1.125rem' }}>...</div>      {/* 字面量,不走 token */}
`})}),`
`,n.jsx(i.hr,{}),`
`,n.jsx(i.h2,{id:"6-完整-stories",children:"6. 完整 Stories"}),`
`,n.jsxs(i.ul,{children:[`
`,n.jsxs(i.li,{children:[n.jsx(i.strong,{children:"Ruler"})," — 8 档 spacing 尺规可视化"]}),`
`,n.jsxs(i.li,{children:[n.jsx(i.strong,{children:"Stacking Demo (real card)"})," — 真实 Plugin 卡片层级 demo"]}),`
`]})]})}function y(e={}){const{wrapper:i}={...l(),...e.components};return i?n.jsx(i,{...e,children:n.jsx(r,{...e})}):r(e)}export{y as default};
