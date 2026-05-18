import type { Meta, StoryObj } from '@storybook/html';
import motionTokens from '../tokens/motion.json';

interface ValueDef { value: string }
interface MotionTokensRoot {
  motion: {
    duration: { [k: string]: ValueDef };
    easing: { [k: string]: ValueDef };
  };
}

const meta: Meta = {
  title: 'Foundation/Motion',
  parameters: {
    layout: 'padded',
    docs: {
      description: {
        component:
          '⚠ 已知问题:`easing.inOut` 与 `easing.default` cubic-bezier 数值完全相同,Day 14-15 修(default 改为 cubic-bezier(0.4, 0, 0.6, 1) 或删除冗余键)。',
      },
    },
  },
  tags: ['autodocs'],
};

export default meta;

const tokens = (motionTokens as MotionTokensRoot).motion;

export const Durations: StoryObj = {
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
      meta.innerHTML = `<div style="font-weight: 600;">${name}</div><code style="font-size: 12px; color: #737373;">${def.value}</code>`;
      const box = document.createElement('div');
      box.style.cssText = `width: 64px; height: 64px; background: #3b82f6; border-radius: 8px; cursor: pointer; transition: transform ${def.value} cubic-bezier(0.4, 0, 0.2, 1);`;
      box.addEventListener('mouseenter', () => { box.style.transform = 'translateX(280px) scale(1.1)'; });
      box.addEventListener('mouseleave', () => { box.style.transform = 'translateX(0) scale(1)'; });
      row.appendChild(meta);
      row.appendChild(box);
      wrap.appendChild(row);
    }
    return wrap;
  },
};

export const Easings: StoryObj = {
  render: () => {
    const wrap = document.createElement('div');
    wrap.style.cssText = "font-family: 'Inter', sans-serif; display: flex; flex-direction: column; gap: 16px;";
    for (const [name, def] of Object.entries(tokens.easing)) {
      const row = document.createElement('div');
      row.style.cssText = 'display: flex; align-items: center; gap: 16px; padding: 16px; background: white; border: 1px solid #e5e5e5; border-radius: 8px;';
      const isDup = name === 'inOut' && def.value === tokens.easing.default?.value;
      const meta = document.createElement('div');
      meta.style.cssText = 'min-width: 220px;';
      meta.innerHTML = `<div style="font-weight: 600;">${name}${isDup ? ' <span style="color: #dc2626; font-size: 11px;">⚠ 与 default 重复</span>' : ''}</div><code style="font-size: 11px; color: #737373; font-family: 'JetBrains Mono', monospace;">${def.value}</code>`;
      const box = document.createElement('div');
      box.style.cssText = `width: 64px; height: 64px; background: #8b5cf6; border-radius: 8px; cursor: pointer; transition: transform 600ms ${def.value};`;
      box.addEventListener('mouseenter', () => { box.style.transform = 'translateX(280px)'; });
      box.addEventListener('mouseleave', () => { box.style.transform = 'translateX(0)'; });
      row.appendChild(meta);
      row.appendChild(box);
      wrap.appendChild(row);
    }
    return wrap;
  },
};
