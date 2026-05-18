const p={sm:{value:"0 1px 2px 0 rgba(0, 0, 0, 0.05)"},md:{value:"0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1)"},lg:{value:"0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -4px rgba(0, 0, 0, 0.1)"},xl:{value:"0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1)"}},c={shadow:p},l={title:"Foundation/Shadow",parameters:{layout:"padded",backgrounds:{default:"light"},docs:{description:{component:"阴影分层。缺 inner / focus-ring / dark-mode 变体,a11y 与暗色模式补全见 Phase 3 / Phase 2。"}}},tags:["autodocs"]},i=c.shadow,e={render:()=>{const a=document.createElement("div");a.style.cssText="font-family: 'Inter', sans-serif; display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 32px; padding: 24px; background: #fafafa; border-radius: 12px;";for(const[s,o]of Object.entries(i)){const r=document.createElement("div");r.style.cssText=`background: white; padding: 24px; border-radius: 8px; box-shadow: ${o.value}; text-align: center;`,r.innerHTML=`<div style="font-size: 13px; font-weight: 600; color: #171717;">shadow-${s}</div><code style="display: block; margin-top: 8px; font-size: 10px; color: #737373; font-family: 'JetBrains Mono', monospace; word-break: break-all;">${o.value}</code>`,a.appendChild(r)}return a}};var n,t,d;e.parameters={...e.parameters,docs:{...(n=e.parameters)==null?void 0:n.docs,source:{originalSource:`{
  render: () => {
    const wrap = document.createElement('div');
    wrap.style.cssText = "font-family: 'Inter', sans-serif; display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 32px; padding: 24px; background: #fafafa; border-radius: 12px;";
    for (const [name, def] of Object.entries(tokens)) {
      const card = document.createElement('div');
      card.style.cssText = \`background: white; padding: 24px; border-radius: 8px; box-shadow: \${def.value}; text-align: center;\`;
      card.innerHTML = \`<div style="font-size: 13px; font-weight: 600; color: #171717;">shadow-\${name}</div><code style="display: block; margin-top: 8px; font-size: 10px; color: #737373; font-family: 'JetBrains Mono', monospace; word-break: break-all;">\${def.value}</code>\`;
      wrap.appendChild(card);
    }
    return wrap;
  }
}`,...(d=(t=e.parameters)==null?void 0:t.docs)==null?void 0:d.source}}};const x=["Layers"];export{e as Layers,x as __namedExportsOrder,l as default};
