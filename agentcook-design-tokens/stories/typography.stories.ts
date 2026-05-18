import type { Meta, StoryObj } from '@storybook/html';
import typoTokens from '../tokens/typography.json';

interface ValueDef { value: string }
interface TypoTokensRoot {
  typography: {
    fontFamily: { [k: string]: ValueDef };
    fontSize: { [k: string]: ValueDef };
    lineHeight: { [k: string]: ValueDef };
    fontWeight: { [k: string]: ValueDef };
  };
}

const meta: Meta = {
  title: 'Foundation/Typography',
  parameters: {
    layout: 'padded',
    docs: {
      description: {
        component:
          'fontFamily / fontSize / lineHeight / fontWeight。⚠ sans 字体栈未含中文 fallback(PingFang SC / Microsoft YaHei),Day 14-15 补。',
      },
    },
  },
  tags: ['autodocs'],
};

export default meta;

const tokens = (typoTokens as TypoTokensRoot).typography;

const card = (title: string, body: HTMLElement): HTMLElement => {
  const wrap = document.createElement('section');
  wrap.style.cssText = 'margin-bottom: 32px;';
  const h = document.createElement('h3');
  h.textContent = title;
  h.style.cssText =
    'font-size: 13px; font-weight: 600; margin: 0 0 12px; text-transform: uppercase; letter-spacing: 0.06em; color: #525252;';
  wrap.appendChild(h);
  wrap.appendChild(body);
  return wrap;
};

export const FontFamilies: StoryObj = {
  render: () => {
    const root = document.createElement('div');
    root.style.cssText = "font-family: 'Inter', sans-serif;";
    const grid = document.createElement('div');
    grid.style.cssText = 'display: grid; gap: 16px;';
    for (const [name, def] of Object.entries(tokens.fontFamily)) {
      const item = document.createElement('div');
      item.style.cssText = `padding: 16px; background: white; border: 1px solid #e5e5e5; border-radius: 8px; font-family: ${def.value};`;
      item.innerHTML = `<div style="font-size: 12px; color: #737373; margin-bottom: 6px; font-family: 'Inter';"><strong>${name}</strong> · <code>${def.value}</code></div><div style="font-size: 18px;">The quick brown fox 中文混排测试 0123456789</div>`;
      grid.appendChild(item);
    }
    root.appendChild(card('Font Family', grid));
    return root;
  },
};

export const FontSizes: StoryObj = {
  render: () => {
    const root = document.createElement('div');
    root.style.cssText = "font-family: 'Inter', sans-serif;";
    const stack = document.createElement('div');
    stack.style.cssText = 'display: flex; flex-direction: column; gap: 8px;';
    for (const [name, def] of Object.entries(tokens.fontSize)) {
      const row = document.createElement('div');
      row.style.cssText = 'padding: 12px 16px; background: white; border: 1px solid #e5e5e5; border-radius: 8px; display: flex; align-items: baseline; gap: 16px;';
      row.innerHTML = `<code style="font-size: 12px; color: #737373; min-width: 60px; font-family: 'JetBrains Mono', monospace;">${name}</code><span style="font-size: ${def.value}; color: #171717;">${def.value} — agentcook design</span>`;
      stack.appendChild(row);
    }
    root.appendChild(card('Font Size', stack));
    return root;
  },
};

export const FontWeights: StoryObj = {
  render: () => {
    const root = document.createElement('div');
    root.style.cssText = "font-family: 'Inter', sans-serif;";
    const stack = document.createElement('div');
    stack.style.cssText = 'display: flex; flex-direction: column; gap: 8px;';
    for (const [name, def] of Object.entries(tokens.fontWeight)) {
      const row = document.createElement('div');
      row.style.cssText = 'padding: 12px 16px; background: white; border: 1px solid #e5e5e5; border-radius: 8px;';
      row.innerHTML = `<div style="font-size: 12px; color: #737373; margin-bottom: 4px;"><strong>${name}</strong> · ${def.value}</div><div style="font-size: 24px; font-weight: ${def.value};">大厂 P7 教你从 0 到 1 上线 AI Agent</div>`;
      stack.appendChild(row);
    }
    root.appendChild(card('Font Weight', stack));
    return root;
  },
};

export const LineHeights: StoryObj = {
  render: () => {
    const root = document.createElement('div');
    root.style.cssText = "font-family: 'Inter', sans-serif;";
    const grid = document.createElement('div');
    grid.style.cssText = 'display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px;';
    const sample =
      'Agent Cook 是一个商业级 AI Agent 产品架构示例。This sample text demonstrates line-height with mixed CJK + Latin content.';
    for (const [name, def] of Object.entries(tokens.lineHeight)) {
      const cell = document.createElement('div');
      cell.style.cssText = 'padding: 16px; background: white; border: 1px solid #e5e5e5; border-radius: 8px;';
      cell.innerHTML = `<div style="font-size: 12px; color: #737373; margin-bottom: 8px;"><strong>${name}</strong> · ${def.value}</div><p style="margin: 0; line-height: ${def.value};">${sample}</p>`;
      grid.appendChild(cell);
    }
    root.appendChild(card('Line Height', grid));
    return root;
  },
};

export const ChineseFallbackMissing: StoryObj = {
  name: 'Chinese Fallback Missing (review evidence)',
  parameters: {
    docs: {
      description: {
        story:
          '⚠ Day 6 review T1 红字证据:`typography.fontFamily.sans` 缺中文 fallback,Win 用户中文回退至中易宋(SimSun),品牌灾难。Day 14-15 修(P0-3)。',
      },
    },
  },
  render: () => {
    const root = document.createElement('div');
    root.style.cssText = "font-family: 'Inter', sans-serif; max-width: 760px;";

    // 警告头部
    const banner = document.createElement('div');
    banner.style.cssText =
      'padding: 16px 20px; background: #fef2f2; border: 1px solid #fecaca; border-radius: 8px; margin-bottom: 24px; color: #991b1b;';
    banner.innerHTML = `
      <div style="font-size: 14px; font-weight: 600; margin-bottom: 6px;">⚠ 中文字体 fallback 缺失</div>
      <div style="font-size: 13px; line-height: 1.6;">
        当前 <code style="background: #fee2e2; padding: 2px 6px; border-radius: 4px; font-family: 'JetBrains Mono', monospace;">typography.fontFamily.sans</code>
        = <code style="background: #fee2e2; padding: 2px 6px; border-radius: 4px; font-family: 'JetBrains Mono', monospace;">'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif</code><br/>
        <strong>Mac/iOS</strong>:系统自带 PingFang SC,中文回退到 PingFang(可读)<br/>
        <strong>Windows Chrome</strong>:无 PingFang/苹方,Inter 不含 CJK,**中文回退到中易宋(SimSun)**——衬线、字重不齐、视觉灾难<br/>
        <strong>修法(Day 14-15)</strong>:sans 栈加 <code style="background: #fee2e2; padding: 2px 6px; border-radius: 4px; font-family: 'JetBrains Mono', monospace;">'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei'</code> 中文链
      </div>
    `;
    root.appendChild(banner);

    // 对比展示 — 当前栈 vs 修复后栈 vs Win-中易宋模拟
    const grid = document.createElement('div');
    grid.style.cssText = 'display: grid; gap: 16px;';

    const sample = 'Agent Cook 商业级 AI Agent 产品 · 大厂 P7 实战教程 · 0123456789';

    const cases = [
      {
        label: '❌ 当前(无中文 fallback)',
        sub: 'Mac 看着 OK 是因为系统自动塞 PingFang SC,Win 上没这个 fallback 就退中易宋',
        family: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
        bg: '#fef2f2',
        border: '#fecaca',
      },
      {
        label: '🔴 模拟 Win Chrome 体验(强制 SimSun)',
        sub: 'Mac 用户看到的就是 Win 用户实际看到的样子',
        family: "'Inter', SimSun, sans-serif",
        bg: '#fffbeb',
        border: '#fde68a',
      },
      {
        label: '✅ Day 14-15 修复后',
        sub: '加了 PingFang SC / Hiragino Sans GB / Microsoft YaHei 三档中文 fallback',
        family:
          "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif",
        bg: '#f0fdf4',
        border: '#bbf7d0',
      },
    ];

    for (const c of cases) {
      const item = document.createElement('div');
      item.style.cssText = `padding: 20px; background: ${c.bg}; border: 1px solid ${c.border}; border-radius: 8px;`;
      item.innerHTML = `
        <div style="font-size: 13px; font-weight: 600; margin-bottom: 4px; color: #171717;">${c.label}</div>
        <div style="font-size: 12px; color: #525252; margin-bottom: 12px;">${c.sub}</div>
        <div style="font-size: 22px; font-family: ${c.family}; color: #171717; padding: 8px 0;">${sample}</div>
        <code style="display: block; margin-top: 8px; font-size: 10px; color: #737373; font-family: 'JetBrains Mono', monospace; word-break: break-all;">font-family: ${c.family}</code>
      `;
      grid.appendChild(item);
    }
    root.appendChild(grid);

    // 修法预览(JSON diff)
    const diff = document.createElement('pre');
    diff.style.cssText =
      "margin-top: 24px; padding: 16px; background: #171717; color: #f5f5f5; border-radius: 8px; font-family: 'JetBrains Mono', monospace; font-size: 12px; line-height: 1.7; overflow-x: auto;";
    diff.innerHTML = `<span style="color: #737373;">// tokens/typography.json (Day 14-15)</span>
"fontFamily": {
  "sans": {
<span style="color: #fca5a5;">-   "value": "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"</span>
<span style="color: #86efac;">+   "value": "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif"</span>
  },
  "mono": {
<span style="color: #fca5a5;">-   "value": "'JetBrains Mono', 'Fira Code', monospace"</span>
<span style="color: #86efac;">+   "value": "'JetBrains Mono', 'Fira Code', 'Sarasa Mono SC', 'PingFang SC', monospace"</span>
  }
}`;
    root.appendChild(diff);

    return root;
  },
};
