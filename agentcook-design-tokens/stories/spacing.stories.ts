import type { Meta, StoryObj } from '@storybook/html';
import spacingTokens from '../tokens/spacing.json';

interface ValueDef { value: string }
interface SpacingTokensRoot {
  spacing: { [k: string]: ValueDef };
}

const meta: Meta = {
  title: 'Foundation/Spacing',
  parameters: {
    layout: 'padded',
    docs: {
      description: {
        component: '4px 基线间距系统。当前 8 档(1/2/3/4/6/8/12/16),缺 0 / 0.5 / 5 / 10 / 20 / 24,Phase 3 落地业务时按需补。',
      },
    },
  },
  tags: ['autodocs'],
};

export default meta;

const tokens = (spacingTokens as SpacingTokensRoot).spacing;

export const Ruler: StoryObj = {
  render: () => {
    const wrap = document.createElement('div');
    wrap.style.cssText = "font-family: 'Inter', sans-serif; display: flex; flex-direction: column; gap: 8px;";
    for (const [name, def] of Object.entries(tokens)) {
      const row = document.createElement('div');
      row.style.cssText = 'display: flex; align-items: center; gap: 16px; padding: 8px 16px; background: white; border: 1px solid #e5e5e5; border-radius: 8px;';
      row.innerHTML = `
        <code style="font-family: 'JetBrains Mono', monospace; font-size: 12px; color: #737373; min-width: 40px;">${name}</code>
        <code style="font-family: 'JetBrains Mono', monospace; font-size: 12px; color: #525252; min-width: 56px;">${def.value}</code>
        <div style="height: 16px; width: ${def.value}; background: #3b82f6; border-radius: 2px;"></div>
      `;
      wrap.appendChild(row);
    }
    return wrap;
  },
};

export const StackingDemo: StoryObj = {
  name: 'Stacking Demo (real card)',
  render: () => {
    const card = document.createElement('div');
    card.style.cssText = `font-family: 'Inter', sans-serif; padding: ${tokens['6'].value}; background: white; border: 1px solid #e5e5e5; border-radius: 12px; max-width: 480px;`;
    card.innerHTML = `
      <h4 style="margin: 0 0 ${tokens['2'].value}; font-size: 16px;">Plugin: weather-fetcher</h4>
      <p style="margin: 0 0 ${tokens['4'].value}; color: #525252; font-size: 14px;">展示 spacing-2 / 4 / 6 在真实卡片里的层级关系。</p>
      <div style="display: flex; gap: ${tokens['2'].value};">
        <span style="padding: ${tokens['1'].value} ${tokens['2'].value}; background: #eff6ff; color: #1d4ed8; border-radius: 4px; font-size: 12px;">stable</span>
        <span style="padding: ${tokens['1'].value} ${tokens['2'].value}; background: #f0fdf4; color: #16a34a; border-radius: 4px; font-size: 12px;">enabled</span>
      </div>
    `;
    return card;
  },
};
