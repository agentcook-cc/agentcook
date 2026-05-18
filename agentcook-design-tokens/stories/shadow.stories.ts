import type { Meta, StoryObj } from '@storybook/html';
import shadowTokens from '../tokens/shadow.json';

interface ValueDef { value: string }
interface ShadowTokensRoot { shadow: { [k: string]: ValueDef } }

const meta: Meta = {
  title: 'Foundation/Shadow',
  parameters: {
    layout: 'padded',
    backgrounds: { default: 'light' },
    docs: {
      description: {
        component: '阴影分层。缺 inner / focus-ring / dark-mode 变体,a11y 与暗色模式补全见 Phase 3 / Phase 2。',
      },
    },
  },
  tags: ['autodocs'],
};

export default meta;

const tokens = (shadowTokens as ShadowTokensRoot).shadow;

export const Layers: StoryObj = {
  render: () => {
    const wrap = document.createElement('div');
    wrap.style.cssText = "font-family: 'Inter', sans-serif; display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 32px; padding: 24px; background: #fafafa; border-radius: 12px;";
    for (const [name, def] of Object.entries(tokens)) {
      const card = document.createElement('div');
      card.style.cssText = `background: white; padding: 24px; border-radius: 8px; box-shadow: ${def.value}; text-align: center;`;
      card.innerHTML = `<div style="font-size: 13px; font-weight: 600; color: #171717;">shadow-${name}</div><code style="display: block; margin-top: 8px; font-size: 10px; color: #737373; font-family: 'JetBrains Mono', monospace; word-break: break-all;">${def.value}</code>`;
      wrap.appendChild(card);
    }
    return wrap;
  },
};
