const f={1:{value:"4px"},2:{value:"8px"},3:{value:"12px"},4:{value:"16px"},6:{value:"24px"},8:{value:"32px"},12:{value:"48px"},16:{value:"64px"}},x={spacing:f},m={title:"Foundation/Spacing",parameters:{layout:"padded",docs:{description:{component:"4px 基线间距系统。当前 8 档(1/2/3/4/6/8/12/16),缺 0 / 0.5 / 5 / 10 / 20 / 24,Phase 3 落地业务时按需补。"}}},tags:["autodocs"]},e=x.spacing,n={render:()=>{const a=document.createElement("div");a.style.cssText="font-family: 'Inter', sans-serif; display: flex; flex-direction: column; gap: 8px;";for(const[u,t]of Object.entries(e)){const r=document.createElement("div");r.style.cssText="display: flex; align-items: center; gap: 16px; padding: 8px 16px; background: white; border: 1px solid #e5e5e5; border-radius: 8px;",r.innerHTML=`
        <code style="font-family: 'JetBrains Mono', monospace; font-size: 12px; color: #737373; min-width: 40px;">${u}</code>
        <code style="font-family: 'JetBrains Mono', monospace; font-size: 12px; color: #525252; min-width: 56px;">${t.value}</code>
        <div style="height: 16px; width: ${t.value}; background: #3b82f6; border-radius: 2px;"></div>
      `,a.appendChild(r)}return a}},o={name:"Stacking Demo (real card)",render:()=>{const a=document.createElement("div");return a.style.cssText=`font-family: 'Inter', sans-serif; padding: ${e[6].value}; background: white; border: 1px solid #e5e5e5; border-radius: 12px; max-width: 480px;`,a.innerHTML=`
      <h4 style="margin: 0 0 ${e[2].value}; font-size: 16px;">Plugin: weather-fetcher</h4>
      <p style="margin: 0 0 ${e[4].value}; color: #525252; font-size: 14px;">展示 spacing-2 / 4 / 6 在真实卡片里的层级关系。</p>
      <div style="display: flex; gap: ${e[2].value};">
        <span style="padding: ${e[1].value} ${e[2].value}; background: #eff6ff; color: #1d4ed8; border-radius: 4px; font-size: 12px;">stable</span>
        <span style="padding: ${e[1].value} ${e[2].value}; background: #f0fdf4; color: #16a34a; border-radius: 4px; font-size: 12px;">enabled</span>
      </div>
    `,a}};var s,d,i;n.parameters={...n.parameters,docs:{...(s=n.parameters)==null?void 0:s.docs,source:{originalSource:`{
  render: () => {
    const wrap = document.createElement('div');
    wrap.style.cssText = "font-family: 'Inter', sans-serif; display: flex; flex-direction: column; gap: 8px;";
    for (const [name, def] of Object.entries(tokens)) {
      const row = document.createElement('div');
      row.style.cssText = 'display: flex; align-items: center; gap: 16px; padding: 8px 16px; background: white; border: 1px solid #e5e5e5; border-radius: 8px;';
      row.innerHTML = \`
        <code style="font-family: 'JetBrains Mono', monospace; font-size: 12px; color: #737373; min-width: 40px;">\${name}</code>
        <code style="font-family: 'JetBrains Mono', monospace; font-size: 12px; color: #525252; min-width: 56px;">\${def.value}</code>
        <div style="height: 16px; width: \${def.value}; background: #3b82f6; border-radius: 2px;"></div>
      \`;
      wrap.appendChild(row);
    }
    return wrap;
  }
}`,...(i=(d=n.parameters)==null?void 0:d.docs)==null?void 0:i.source}}};var p,l,c;o.parameters={...o.parameters,docs:{...(p=o.parameters)==null?void 0:p.docs,source:{originalSource:`{
  name: 'Stacking Demo (real card)',
  render: () => {
    const card = document.createElement('div');
    card.style.cssText = \`font-family: 'Inter', sans-serif; padding: \${tokens['6'].value}; background: white; border: 1px solid #e5e5e5; border-radius: 12px; max-width: 480px;\`;
    card.innerHTML = \`
      <h4 style="margin: 0 0 \${tokens['2'].value}; font-size: 16px;">Plugin: weather-fetcher</h4>
      <p style="margin: 0 0 \${tokens['4'].value}; color: #525252; font-size: 14px;">展示 spacing-2 / 4 / 6 在真实卡片里的层级关系。</p>
      <div style="display: flex; gap: \${tokens['2'].value};">
        <span style="padding: \${tokens['1'].value} \${tokens['2'].value}; background: #eff6ff; color: #1d4ed8; border-radius: 4px; font-size: 12px;">stable</span>
        <span style="padding: \${tokens['1'].value} \${tokens['2'].value}; background: #f0fdf4; color: #16a34a; border-radius: 4px; font-size: 12px;">enabled</span>
      </div>
    \`;
    return card;
  }
}`,...(c=(l=o.parameters)==null?void 0:l.docs)==null?void 0:c.source}}};const g=["Ruler","StackingDemo"],v=Object.freeze(Object.defineProperty({__proto__:null,Ruler:n,StackingDemo:o,__namedExportsOrder:g,default:m},Symbol.toStringTag,{value:"Module"}));export{n as R,v as S,o as a};
