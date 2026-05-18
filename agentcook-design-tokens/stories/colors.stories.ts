import type { Meta, StoryObj } from '@storybook/html';
import colorTokens from '../tokens/color.json';

interface ShadeDef { value: string }
interface ColorTokensRoot {
  color: { [palette: string]: { [shade: string]: ShadeDef } };
}

const meta: Meta = {
  title: 'Foundation/Colors',
  parameters: {
    layout: 'padded',
    docs: {
      description: {
        component:
          '6 色系 atomic 层。primary / secondary 缺中间色阶(待 Day 14-15 补);semantic 层(text.primary / bg.surface 等)未建,Phase 1 末引入。',
      },
    },
  },
  tags: ['autodocs'],
};

export default meta;

const renderPalette = (): HTMLElement => {
  const tokens = (colorTokens as ColorTokensRoot).color;
  const wrapper = document.createElement('div');
  wrapper.style.cssText =
    "font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; color: #171717;";

  for (const [paletteName, shades] of Object.entries(tokens)) {
    const section = document.createElement('section');
    section.style.cssText = 'margin-bottom: 32px;';

    const title = document.createElement('h3');
    title.textContent = paletteName;
    title.style.cssText =
      'font-size: 13px; font-weight: 600; margin: 0 0 12px; text-transform: uppercase; letter-spacing: 0.06em; color: #525252;';
    section.appendChild(title);

    const grid = document.createElement('div');
    grid.style.cssText =
      'display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 12px;';

    for (const [shade, def] of Object.entries(shades)) {
      const card = document.createElement('div');
      card.style.cssText =
        'border-radius: 8px; overflow: hidden; box-shadow: 0 1px 2px rgba(0,0,0,0.05); border: 1px solid #e5e5e5;';

      const swatch = document.createElement('div');
      swatch.style.cssText = `height: 64px; background: ${def.value};`;
      card.appendChild(swatch);

      const label = document.createElement('div');
      label.style.cssText =
        'padding: 8px 10px; background: white; font-size: 12px; line-height: 1.5;';
      label.innerHTML = `<strong>${paletteName}-${shade}</strong><br/><code style="color: #737373; font-family: 'JetBrains Mono', monospace;">${def.value}</code>`;
      card.appendChild(label);

      grid.appendChild(card);
    }
    section.appendChild(grid);
    wrapper.appendChild(section);
  }
  return wrapper;
};

export const Palette: StoryObj = {
  name: 'Full Palette',
  render: renderPalette,
};

export const PrimaryGap: StoryObj = {
  name: 'Primary Gap (review evidence)',
  render: () => {
    const div = document.createElement('div');
    div.style.cssText = "font-family: 'Inter', sans-serif; color: #525252; max-width: 640px;";
    div.innerHTML = `
      <p style="margin: 0 0 12px;"><strong>当前 primary 只有 5 档(50/100/500/600/700)</strong>,缺 200/300/400/800/900。</p>
      <p style="margin: 0 0 12px; font-size: 13px;">影响:hover / focus / disabled / pressed 状态做不出连续灰阶,admin form a11y focus ring 没料。</p>
      <p style="margin: 0; font-size: 13px; color: #737373;">→ Day 14-15 补全 10 档(对齐 neutral 色阶规模)</p>
    `;
    return div;
  },
};
