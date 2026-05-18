import type { Meta, StoryObj } from '@storybook/html';
import radiusTokens from '../tokens/radius.json';

interface ValueDef { value: string }
interface RadiusTokensRoot { radius: { [k: string]: ValueDef } }

const meta: Meta = {
  title: 'Foundation/Radius',
  parameters: {
    layout: 'padded',
    docs: {
      description: {
        component: '当前 4 档(sm / md / lg / full)。缺 none / xs / xl / 2xl(chat 气泡常用),Phase 3 chat UI 落地时补。',
      },
    },
  },
  tags: ['autodocs'],
};

export default meta;

const tokens = (radiusTokens as RadiusTokensRoot).radius;

export const All: StoryObj = {
  render: () => {
    const wrap = document.createElement('div');
    wrap.style.cssText = "font-family: 'Inter', sans-serif; display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 16px;";
    for (const [name, def] of Object.entries(tokens)) {
      const cell = document.createElement('div');
      cell.style.cssText = 'background: white; padding: 16px; border: 1px solid #e5e5e5; border-radius: 8px; text-align: center;';
      const visual = document.createElement('div');
      visual.style.cssText = `width: 80px; height: 80px; background: #3b82f6; margin: 0 auto 12px; border-radius: ${def.value};`;
      cell.appendChild(visual);
      const label = document.createElement('div');
      label.style.cssText = "font-size: 12px; color: #737373; font-family: 'JetBrains Mono', monospace;";
      label.innerHTML = `<strong style="color: #171717;">${name}</strong> · ${def.value}`;
      cell.appendChild(label);
      wrap.appendChild(cell);
    }
    return wrap;
  },
};
