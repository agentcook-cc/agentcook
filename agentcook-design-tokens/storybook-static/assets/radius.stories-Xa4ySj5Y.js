const i={sm:{value:"4px"},md:{value:"8px"},lg:{value:"12px"},full:{value:"9999px"}},p={radius:i},m={title:"Foundation/Radius",parameters:{layout:"padded",docs:{description:{component:"当前 4 档(sm / md / lg / full)。缺 none / xs / xl / 2xl(chat 气泡常用),Phase 3 chat UI 落地时补。"}}},tags:["autodocs"]},u=p.radius,t={render:()=>{const n=document.createElement("div");n.style.cssText="font-family: 'Inter', sans-serif; display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 16px;";for(const[c,s]of Object.entries(u)){const e=document.createElement("div");e.style.cssText="background: white; padding: 16px; border: 1px solid #e5e5e5; border-radius: 8px; text-align: center;";const l=document.createElement("div");l.style.cssText=`width: 80px; height: 80px; background: #3b82f6; margin: 0 auto 12px; border-radius: ${s.value};`,e.appendChild(l);const a=document.createElement("div");a.style.cssText="font-size: 12px; color: #737373; font-family: 'JetBrains Mono', monospace;",a.innerHTML=`<strong style="color: #171717;">${c}</strong> · ${s.value}`,e.appendChild(a),n.appendChild(e)}return n}};var r,o,d;t.parameters={...t.parameters,docs:{...(r=t.parameters)==null?void 0:r.docs,source:{originalSource:`{
  render: () => {
    const wrap = document.createElement('div');
    wrap.style.cssText = "font-family: 'Inter', sans-serif; display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 16px;";
    for (const [name, def] of Object.entries(tokens)) {
      const cell = document.createElement('div');
      cell.style.cssText = 'background: white; padding: 16px; border: 1px solid #e5e5e5; border-radius: 8px; text-align: center;';
      const visual = document.createElement('div');
      visual.style.cssText = \`width: 80px; height: 80px; background: #3b82f6; margin: 0 auto 12px; border-radius: \${def.value};\`;
      cell.appendChild(visual);
      const label = document.createElement('div');
      label.style.cssText = "font-size: 12px; color: #737373; font-family: 'JetBrains Mono', monospace;";
      label.innerHTML = \`<strong style="color: #171717;">\${name}</strong> · \${def.value}\`;
      cell.appendChild(label);
      wrap.appendChild(cell);
    }
    return wrap;
  }
}`,...(d=(o=t.parameters)==null?void 0:o.docs)==null?void 0:d.source}}};const x=["All"];export{t as All,x as __namedExportsOrder,m as default};
