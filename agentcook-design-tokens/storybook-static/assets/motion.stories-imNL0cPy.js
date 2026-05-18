const v={duration:{fast:{value:"150ms"},normal:{value:"250ms"},slow:{value:"400ms"}},easing:{default:{value:"cubic-bezier(0.4, 0, 0.2, 1)",comment:"Material Design standard — asymmetric, 偏快 in / 平稳 out,日常 UI 默认"},in:{value:"cubic-bezier(0.4, 0, 1, 1)",comment:"ease-in"},out:{value:"cubic-bezier(0, 0, 0.2, 1)",comment:"ease-out"},inOut:{value:"cubic-bezier(0.42, 0, 0.58, 1)",comment:"W3C 经典 ease-in-out symmetric — Day 14 P0-5 修(原值与 default 完全相同)"}}},y={motion:v},g={title:"Foundation/Motion",parameters:{layout:"padded",docs:{description:{component:"⚠ 已知问题:`easing.inOut` 与 `easing.default` cubic-bezier 数值完全相同,Day 14-15 修(default 改为 cubic-bezier(0.4, 0, 0.6, 1) 或删除冗余键)。"}}},tags:["autodocs"]},l=y.motion,d={render:()=>{const t=document.createElement("div");t.style.cssText="font-family: 'Inter', sans-serif; display: flex; flex-direction: column; gap: 16px;";const s=document.createElement("p");s.style.cssText="margin: 0; padding: 12px 16px; background: #fffbeb; border: 1px solid #fde68a; border-radius: 8px; font-size: 13px; color: #92400e;",s.innerHTML="👉 鼠标悬停每个方块,观察不同 duration 下的 transform 平移速度差异",t.appendChild(s);for(const[i,o]of Object.entries(l.duration)){const n=document.createElement("div");n.style.cssText="display: flex; align-items: center; gap: 16px; padding: 16px; background: white; border: 1px solid #e5e5e5; border-radius: 8px;";const a=document.createElement("div");a.style.cssText="min-width: 120px;",a.innerHTML=`<div style="font-weight: 600;">${i}</div><code style="font-size: 12px; color: #737373;">${o.value}</code>`;const e=document.createElement("div");e.style.cssText=`width: 64px; height: 64px; background: #3b82f6; border-radius: 8px; cursor: pointer; transition: transform ${o.value} cubic-bezier(0.4, 0, 0.2, 1);`,e.addEventListener("mouseenter",()=>{e.style.transform="translateX(280px) scale(1.1)"}),e.addEventListener("mouseleave",()=>{e.style.transform="translateX(0) scale(1)"}),n.appendChild(a),n.appendChild(e),t.appendChild(n)}return t}},c={render:()=>{var s;const t=document.createElement("div");t.style.cssText="font-family: 'Inter', sans-serif; display: flex; flex-direction: column; gap: 16px;";for(const[i,o]of Object.entries(l.easing)){const n=document.createElement("div");n.style.cssText="display: flex; align-items: center; gap: 16px; padding: 16px; background: white; border: 1px solid #e5e5e5; border-radius: 8px;";const a=i==="inOut"&&o.value===((s=l.easing.default)==null?void 0:s.value),e=document.createElement("div");e.style.cssText="min-width: 220px;",e.innerHTML=`<div style="font-weight: 600;">${i}${a?' <span style="color: #dc2626; font-size: 11px;">⚠ 与 default 重复</span>':""}</div><code style="font-size: 11px; color: #737373; font-family: 'JetBrains Mono', monospace;">${o.value}</code>`;const r=document.createElement("div");r.style.cssText=`width: 64px; height: 64px; background: #8b5cf6; border-radius: 8px; cursor: pointer; transition: transform 600ms ${o.value};`,r.addEventListener("mouseenter",()=>{r.style.transform="translateX(280px)"}),r.addEventListener("mouseleave",()=>{r.style.transform="translateX(0)"}),n.appendChild(e),n.appendChild(r),t.appendChild(n)}return t}};var p,m,u;d.parameters={...d.parameters,docs:{...(p=d.parameters)==null?void 0:p.docs,source:{originalSource:`{
  render: () => {
    const wrap = document.createElement('div');
    wrap.style.cssText = "font-family: 'Inter', sans-serif; display: flex; flex-direction: column; gap: 16px;";
    const note = document.createElement('p');
    note.style.cssText = 'margin: 0; padding: 12px 16px; background: #fffbeb; border: 1px solid #fde68a; border-radius: 8px; font-size: 13px; color: #92400e;';
    note.innerHTML = '👉 鼠标悬停每个方块,观察不同 duration 下的 transform 平移速度差异';
    wrap.appendChild(note);
    for (const [name, def] of Object.entries(tokens.duration)) {
      const row = document.createElement('div');
      row.style.cssText = 'display: flex; align-items: center; gap: 16px; padding: 16px; background: white; border: 1px solid #e5e5e5; border-radius: 8px;';
      const meta = document.createElement('div');
      meta.style.cssText = 'min-width: 120px;';
      meta.innerHTML = \`<div style="font-weight: 600;">\${name}</div><code style="font-size: 12px; color: #737373;">\${def.value}</code>\`;
      const box = document.createElement('div');
      box.style.cssText = \`width: 64px; height: 64px; background: #3b82f6; border-radius: 8px; cursor: pointer; transition: transform \${def.value} cubic-bezier(0.4, 0, 0.2, 1);\`;
      box.addEventListener('mouseenter', () => {
        box.style.transform = 'translateX(280px) scale(1.1)';
      });
      box.addEventListener('mouseleave', () => {
        box.style.transform = 'translateX(0) scale(1)';
      });
      row.appendChild(meta);
      row.appendChild(box);
      wrap.appendChild(row);
    }
    return wrap;
  }
}`,...(u=(m=d.parameters)==null?void 0:m.docs)==null?void 0:u.source}}};var x,f,b;c.parameters={...c.parameters,docs:{...(x=c.parameters)==null?void 0:x.docs,source:{originalSource:`{
  render: () => {
    const wrap = document.createElement('div');
    wrap.style.cssText = "font-family: 'Inter', sans-serif; display: flex; flex-direction: column; gap: 16px;";
    for (const [name, def] of Object.entries(tokens.easing)) {
      const row = document.createElement('div');
      row.style.cssText = 'display: flex; align-items: center; gap: 16px; padding: 16px; background: white; border: 1px solid #e5e5e5; border-radius: 8px;';
      const isDup = name === 'inOut' && def.value === tokens.easing.default?.value;
      const meta = document.createElement('div');
      meta.style.cssText = 'min-width: 220px;';
      meta.innerHTML = \`<div style="font-weight: 600;">\${name}\${isDup ? ' <span style="color: #dc2626; font-size: 11px;">⚠ 与 default 重复</span>' : ''}</div><code style="font-size: 11px; color: #737373; font-family: 'JetBrains Mono', monospace;">\${def.value}</code>\`;
      const box = document.createElement('div');
      box.style.cssText = \`width: 64px; height: 64px; background: #8b5cf6; border-radius: 8px; cursor: pointer; transition: transform 600ms \${def.value};\`;
      box.addEventListener('mouseenter', () => {
        box.style.transform = 'translateX(280px)';
      });
      box.addEventListener('mouseleave', () => {
        box.style.transform = 'translateX(0)';
      });
      row.appendChild(meta);
      row.appendChild(box);
      wrap.appendChild(row);
    }
    return wrap;
  }
}`,...(b=(f=c.parameters)==null?void 0:f.docs)==null?void 0:b.source}}};const w=["Durations","Easings"];export{d as Durations,c as Easings,w as __namedExportsOrder,g as default};
