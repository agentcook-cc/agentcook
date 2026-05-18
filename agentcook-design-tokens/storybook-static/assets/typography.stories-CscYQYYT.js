const $={fontFamily:{sans:{value:"'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans SC', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif",comment:"Day 14 P0-4:加 Noto Sans SC / PingFang SC / Hiragino Sans GB / Microsoft YaHei 4 档中文 fallback。Win Chrome 不再退中易宋。"},mono:{value:"'JetBrains Mono', 'Fira Code', 'Sarasa Mono SC', 'PingFang SC', monospace",comment:"Day 14 P0-4:加 Sarasa Mono SC / PingFang SC 中文等宽 fallback,代码块嵌中文不跳字"}},fontSize:{xs:{value:"0.75rem"},sm:{value:"0.875rem"},base:{value:"1rem"},lg:{value:"1.125rem"},xl:{value:"1.25rem"},"2xl":{value:"1.5rem"},"3xl":{value:"1.875rem"},"4xl":{value:"2.25rem"}},lineHeight:{tight:{value:"1.25"},normal:{value:"1.5"},relaxed:{value:"1.75"}},fontWeight:{normal:{value:"400"},medium:{value:"500"},semibold:{value:"600"},bold:{value:"700"}}},z={typography:$},B={title:"Foundation/Typography",parameters:{layout:"padded",docs:{description:{component:"fontFamily / fontSize / lineHeight / fontWeight。⚠ sans 字体栈未含中文 fallback(PingFang SC / Microsoft YaHei),Day 14-15 补。"}}},tags:["autodocs"]},m=z.typography,f=(e,n)=>{const o=document.createElement("section");o.style.cssText="margin-bottom: 32px;";const t=document.createElement("h3");return t.textContent=e,t.style.cssText="font-size: 13px; font-weight: 600; margin: 0 0 12px; text-transform: uppercase; letter-spacing: 0.06em; color: #525252;",o.appendChild(t),o.appendChild(n),o},i={render:()=>{const e=document.createElement("div");e.style.cssText="font-family: 'Inter', sans-serif;";const n=document.createElement("div");n.style.cssText="display: grid; gap: 16px;";for(const[o,t]of Object.entries(m.fontFamily)){const a=document.createElement("div");a.style.cssText=`padding: 16px; background: white; border: 1px solid #e5e5e5; border-radius: 8px; font-family: ${t.value};`,a.innerHTML=`<div style="font-size: 12px; color: #737373; margin-bottom: 6px; font-family: 'Inter';"><strong>${o}</strong> · <code>${t.value}</code></div><div style="font-size: 18px;">The quick brown fox 中文混排测试 0123456789</div>`,n.appendChild(a)}return e.appendChild(f("Font Family",n)),e}},d={render:()=>{const e=document.createElement("div");e.style.cssText="font-family: 'Inter', sans-serif;";const n=document.createElement("div");n.style.cssText="display: flex; flex-direction: column; gap: 8px;";for(const[o,t]of Object.entries(m.fontSize)){const a=document.createElement("div");a.style.cssText="padding: 12px 16px; background: white; border: 1px solid #e5e5e5; border-radius: 8px; display: flex; align-items: baseline; gap: 16px;",a.innerHTML=`<code style="font-size: 12px; color: #737373; min-width: 60px; font-family: 'JetBrains Mono', monospace;">${o}</code><span style="font-size: ${t.value}; color: #171717;">${t.value} — agentcook design</span>`,n.appendChild(a)}return e.appendChild(f("Font Size",n)),e}},l={render:()=>{const e=document.createElement("div");e.style.cssText="font-family: 'Inter', sans-serif;";const n=document.createElement("div");n.style.cssText="display: flex; flex-direction: column; gap: 8px;";for(const[o,t]of Object.entries(m.fontWeight)){const a=document.createElement("div");a.style.cssText="padding: 12px 16px; background: white; border: 1px solid #e5e5e5; border-radius: 8px;",a.innerHTML=`<div style="font-size: 12px; color: #737373; margin-bottom: 4px;"><strong>${o}</strong> · ${t.value}</div><div style="font-size: 24px; font-weight: ${t.value};">大厂 P7 教你从 0 到 1 上线 AI Agent</div>`,n.appendChild(a)}return e.appendChild(f("Font Weight",n)),e}},c={render:()=>{const e=document.createElement("div");e.style.cssText="font-family: 'Inter', sans-serif;";const n=document.createElement("div");n.style.cssText="display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px;";const o="Agent Cook 是一个商业级 AI Agent 产品架构示例。This sample text demonstrates line-height with mixed CJK + Latin content.";for(const[t,a]of Object.entries(m.lineHeight)){const s=document.createElement("div");s.style.cssText="padding: 16px; background: white; border: 1px solid #e5e5e5; border-radius: 8px;",s.innerHTML=`<div style="font-size: 12px; color: #737373; margin-bottom: 8px;"><strong>${t}</strong> · ${a.value}</div><p style="margin: 0; line-height: ${a.value};">${o}</p>`,n.appendChild(s)}return e.appendChild(f("Line Height",n)),e}},p={name:"Chinese Fallback Missing (review evidence)",parameters:{docs:{description:{story:"⚠ Day 6 review T1 红字证据:`typography.fontFamily.sans` 缺中文 fallback,Win 用户中文回退至中易宋(SimSun),品牌灾难。Day 14-15 修(P0-3)。"}}},render:()=>{const e=document.createElement("div");e.style.cssText="font-family: 'Inter', sans-serif; max-width: 760px;";const n=document.createElement("div");n.style.cssText="padding: 16px 20px; background: #fef2f2; border: 1px solid #fecaca; border-radius: 8px; margin-bottom: 24px; color: #991b1b;",n.innerHTML=`
      <div style="font-size: 14px; font-weight: 600; margin-bottom: 6px;">⚠ 中文字体 fallback 缺失</div>
      <div style="font-size: 13px; line-height: 1.6;">
        当前 <code style="background: #fee2e2; padding: 2px 6px; border-radius: 4px; font-family: 'JetBrains Mono', monospace;">typography.fontFamily.sans</code>
        = <code style="background: #fee2e2; padding: 2px 6px; border-radius: 4px; font-family: 'JetBrains Mono', monospace;">'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif</code><br/>
        <strong>Mac/iOS</strong>:系统自带 PingFang SC,中文回退到 PingFang(可读)<br/>
        <strong>Windows Chrome</strong>:无 PingFang/苹方,Inter 不含 CJK,**中文回退到中易宋(SimSun)**——衬线、字重不齐、视觉灾难<br/>
        <strong>修法(Day 14-15)</strong>:sans 栈加 <code style="background: #fee2e2; padding: 2px 6px; border-radius: 4px; font-family: 'JetBrains Mono', monospace;">'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei'</code> 中文链
      </div>
    `,e.appendChild(n);const o=document.createElement("div");o.style.cssText="display: grid; gap: 16px;";const t="Agent Cook 商业级 AI Agent 产品 · 大厂 P7 实战教程 · 0123456789",a=[{label:"❌ 当前(无中文 fallback)",sub:"Mac 看着 OK 是因为系统自动塞 PingFang SC,Win 上没这个 fallback 就退中易宋",family:"'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",bg:"#fef2f2",border:"#fecaca"},{label:"🔴 模拟 Win Chrome 体验(强制 SimSun)",sub:"Mac 用户看到的就是 Win 用户实际看到的样子",family:"'Inter', SimSun, sans-serif",bg:"#fffbeb",border:"#fde68a"},{label:"✅ Day 14-15 修复后",sub:"加了 PingFang SC / Hiragino Sans GB / Microsoft YaHei 三档中文 fallback",family:"'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif",bg:"#f0fdf4",border:"#bbf7d0"}];for(const r of a){const g=document.createElement("div");g.style.cssText=`padding: 20px; background: ${r.bg}; border: 1px solid ${r.border}; border-radius: 8px;`,g.innerHTML=`
        <div style="font-size: 13px; font-weight: 600; margin-bottom: 4px; color: #171717;">${r.label}</div>
        <div style="font-size: 12px; color: #525252; margin-bottom: 12px;">${r.sub}</div>
        <div style="font-size: 22px; font-family: ${r.family}; color: #171717; padding: 8px 0;">${t}</div>
        <code style="display: block; margin-top: 8px; font-size: 10px; color: #737373; font-family: 'JetBrains Mono', monospace; word-break: break-all;">font-family: ${r.family}</code>
      `,o.appendChild(g)}e.appendChild(o);const s=document.createElement("pre");return s.style.cssText="margin-top: 24px; padding: 16px; background: #171717; color: #f5f5f5; border-radius: 8px; font-family: 'JetBrains Mono', monospace; font-size: 12px; line-height: 1.7; overflow-x: auto;",s.innerHTML=`<span style="color: #737373;">// tokens/typography.json (Day 14-15)</span>
"fontFamily": {
  "sans": {
<span style="color: #fca5a5;">-   "value": "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"</span>
<span style="color: #86efac;">+   "value": "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif"</span>
  },
  "mono": {
<span style="color: #fca5a5;">-   "value": "'JetBrains Mono', 'Fira Code', monospace"</span>
<span style="color: #86efac;">+   "value": "'JetBrains Mono', 'Fira Code', 'Sarasa Mono SC', 'PingFang SC', monospace"</span>
  }
}`,e.appendChild(s),e}};var y,x,u;i.parameters={...i.parameters,docs:{...(y=i.parameters)==null?void 0:y.docs,source:{originalSource:`{
  render: () => {
    const root = document.createElement('div');
    root.style.cssText = "font-family: 'Inter', sans-serif;";
    const grid = document.createElement('div');
    grid.style.cssText = 'display: grid; gap: 16px;';
    for (const [name, def] of Object.entries(tokens.fontFamily)) {
      const item = document.createElement('div');
      item.style.cssText = \`padding: 16px; background: white; border: 1px solid #e5e5e5; border-radius: 8px; font-family: \${def.value};\`;
      item.innerHTML = \`<div style="font-size: 12px; color: #737373; margin-bottom: 6px; font-family: 'Inter';"><strong>\${name}</strong> · <code>\${def.value}</code></div><div style="font-size: 18px;">The quick brown fox 中文混排测试 0123456789</div>\`;
      grid.appendChild(item);
    }
    root.appendChild(card('Font Family', grid));
    return root;
  }
}`,...(u=(x=i.parameters)==null?void 0:x.docs)==null?void 0:u.source}}};var b,v,h;d.parameters={...d.parameters,docs:{...(b=d.parameters)==null?void 0:b.docs,source:{originalSource:`{
  render: () => {
    const root = document.createElement('div');
    root.style.cssText = "font-family: 'Inter', sans-serif;";
    const stack = document.createElement('div');
    stack.style.cssText = 'display: flex; flex-direction: column; gap: 8px;';
    for (const [name, def] of Object.entries(tokens.fontSize)) {
      const row = document.createElement('div');
      row.style.cssText = 'padding: 12px 16px; background: white; border: 1px solid #e5e5e5; border-radius: 8px; display: flex; align-items: baseline; gap: 16px;';
      row.innerHTML = \`<code style="font-size: 12px; color: #737373; min-width: 60px; font-family: 'JetBrains Mono', monospace;">\${name}</code><span style="font-size: \${def.value}; color: #171717;">\${def.value} — agentcook design</span>\`;
      stack.appendChild(row);
    }
    root.appendChild(card('Font Size', stack));
    return root;
  }
}`,...(h=(v=d.parameters)==null?void 0:v.docs)==null?void 0:h.source}}};var S,k,C;l.parameters={...l.parameters,docs:{...(S=l.parameters)==null?void 0:S.docs,source:{originalSource:`{
  render: () => {
    const root = document.createElement('div');
    root.style.cssText = "font-family: 'Inter', sans-serif;";
    const stack = document.createElement('div');
    stack.style.cssText = 'display: flex; flex-direction: column; gap: 8px;';
    for (const [name, def] of Object.entries(tokens.fontWeight)) {
      const row = document.createElement('div');
      row.style.cssText = 'padding: 12px 16px; background: white; border: 1px solid #e5e5e5; border-radius: 8px;';
      row.innerHTML = \`<div style="font-size: 12px; color: #737373; margin-bottom: 4px;"><strong>\${name}</strong> · \${def.value}</div><div style="font-size: 24px; font-weight: \${def.value};">大厂 P7 教你从 0 到 1 上线 AI Agent</div>\`;
      stack.appendChild(row);
    }
    root.appendChild(card('Font Weight', stack));
    return root;
  }
}`,...(C=(k=l.parameters)==null?void 0:k.docs)==null?void 0:C.source}}};var F,M,T;c.parameters={...c.parameters,docs:{...(F=c.parameters)==null?void 0:F.docs,source:{originalSource:`{
  render: () => {
    const root = document.createElement('div');
    root.style.cssText = "font-family: 'Inter', sans-serif;";
    const grid = document.createElement('div');
    grid.style.cssText = 'display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px;';
    const sample = 'Agent Cook 是一个商业级 AI Agent 产品架构示例。This sample text demonstrates line-height with mixed CJK + Latin content.';
    for (const [name, def] of Object.entries(tokens.lineHeight)) {
      const cell = document.createElement('div');
      cell.style.cssText = 'padding: 16px; background: white; border: 1px solid #e5e5e5; border-radius: 8px;';
      cell.innerHTML = \`<div style="font-size: 12px; color: #737373; margin-bottom: 8px;"><strong>\${name}</strong> · \${def.value}</div><p style="margin: 0; line-height: \${def.value};">\${sample}</p>\`;
      grid.appendChild(cell);
    }
    root.appendChild(card('Line Height', grid));
    return root;
  }
}`,...(T=(M=c.parameters)==null?void 0:M.docs)==null?void 0:T.source}}};var w,I,H;p.parameters={...p.parameters,docs:{...(w=p.parameters)==null?void 0:w.docs,source:{originalSource:`{
  name: 'Chinese Fallback Missing (review evidence)',
  parameters: {
    docs: {
      description: {
        story: '⚠ Day 6 review T1 红字证据:\`typography.fontFamily.sans\` 缺中文 fallback,Win 用户中文回退至中易宋(SimSun),品牌灾难。Day 14-15 修(P0-3)。'
      }
    }
  },
  render: () => {
    const root = document.createElement('div');
    root.style.cssText = "font-family: 'Inter', sans-serif; max-width: 760px;";

    // 警告头部
    const banner = document.createElement('div');
    banner.style.cssText = 'padding: 16px 20px; background: #fef2f2; border: 1px solid #fecaca; border-radius: 8px; margin-bottom: 24px; color: #991b1b;';
    banner.innerHTML = \`
      <div style="font-size: 14px; font-weight: 600; margin-bottom: 6px;">⚠ 中文字体 fallback 缺失</div>
      <div style="font-size: 13px; line-height: 1.6;">
        当前 <code style="background: #fee2e2; padding: 2px 6px; border-radius: 4px; font-family: 'JetBrains Mono', monospace;">typography.fontFamily.sans</code>
        = <code style="background: #fee2e2; padding: 2px 6px; border-radius: 4px; font-family: 'JetBrains Mono', monospace;">'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif</code><br/>
        <strong>Mac/iOS</strong>:系统自带 PingFang SC,中文回退到 PingFang(可读)<br/>
        <strong>Windows Chrome</strong>:无 PingFang/苹方,Inter 不含 CJK,**中文回退到中易宋(SimSun)**——衬线、字重不齐、视觉灾难<br/>
        <strong>修法(Day 14-15)</strong>:sans 栈加 <code style="background: #fee2e2; padding: 2px 6px; border-radius: 4px; font-family: 'JetBrains Mono', monospace;">'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei'</code> 中文链
      </div>
    \`;
    root.appendChild(banner);

    // 对比展示 — 当前栈 vs 修复后栈 vs Win-中易宋模拟
    const grid = document.createElement('div');
    grid.style.cssText = 'display: grid; gap: 16px;';
    const sample = 'Agent Cook 商业级 AI Agent 产品 · 大厂 P7 实战教程 · 0123456789';
    const cases = [{
      label: '❌ 当前(无中文 fallback)',
      sub: 'Mac 看着 OK 是因为系统自动塞 PingFang SC,Win 上没这个 fallback 就退中易宋',
      family: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
      bg: '#fef2f2',
      border: '#fecaca'
    }, {
      label: '🔴 模拟 Win Chrome 体验(强制 SimSun)',
      sub: 'Mac 用户看到的就是 Win 用户实际看到的样子',
      family: "'Inter', SimSun, sans-serif",
      bg: '#fffbeb',
      border: '#fde68a'
    }, {
      label: '✅ Day 14-15 修复后',
      sub: '加了 PingFang SC / Hiragino Sans GB / Microsoft YaHei 三档中文 fallback',
      family: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif",
      bg: '#f0fdf4',
      border: '#bbf7d0'
    }];
    for (const c of cases) {
      const item = document.createElement('div');
      item.style.cssText = \`padding: 20px; background: \${c.bg}; border: 1px solid \${c.border}; border-radius: 8px;\`;
      item.innerHTML = \`
        <div style="font-size: 13px; font-weight: 600; margin-bottom: 4px; color: #171717;">\${c.label}</div>
        <div style="font-size: 12px; color: #525252; margin-bottom: 12px;">\${c.sub}</div>
        <div style="font-size: 22px; font-family: \${c.family}; color: #171717; padding: 8px 0;">\${sample}</div>
        <code style="display: block; margin-top: 8px; font-size: 10px; color: #737373; font-family: 'JetBrains Mono', monospace; word-break: break-all;">font-family: \${c.family}</code>
      \`;
      grid.appendChild(item);
    }
    root.appendChild(grid);

    // 修法预览(JSON diff)
    const diff = document.createElement('pre');
    diff.style.cssText = "margin-top: 24px; padding: 16px; background: #171717; color: #f5f5f5; border-radius: 8px; font-family: 'JetBrains Mono', monospace; font-size: 12px; line-height: 1.7; overflow-x: auto;";
    diff.innerHTML = \`<span style="color: #737373;">// tokens/typography.json (Day 14-15)</span>
"fontFamily": {
  "sans": {
<span style="color: #fca5a5;">-   "value": "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"</span>
<span style="color: #86efac;">+   "value": "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif"</span>
  },
  "mono": {
<span style="color: #fca5a5;">-   "value": "'JetBrains Mono', 'Fira Code', monospace"</span>
<span style="color: #86efac;">+   "value": "'JetBrains Mono', 'Fira Code', 'Sarasa Mono SC', 'PingFang SC', monospace"</span>
  }
}\`;
    root.appendChild(diff);
    return root;
  }
}`,...(H=(I=p.parameters)==null?void 0:I.docs)==null?void 0:H.source}}};const E=["FontFamilies","FontSizes","FontWeights","LineHeights","ChineseFallbackMissing"],P=Object.freeze(Object.defineProperty({__proto__:null,ChineseFallbackMissing:p,FontFamilies:i,FontSizes:d,FontWeights:l,LineHeights:c,__namedExportsOrder:E,default:B},Symbol.toStringTag,{value:"Module"}));export{p as C,i as F,c as L,P as T,d as a,l as b};
