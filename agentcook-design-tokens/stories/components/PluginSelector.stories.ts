import type { Meta, StoryObj } from '@storybook/html';

const meta: Meta = {
  title: 'Components/PluginSelector',
  parameters: {
    layout: 'padded',
    docs: {
      description: {
        component:
          'Visual mock of `app/src/components/PluginSelector.tsx` — proves the dropdown trigger + listbox + status badge palette read from tokens. Real component lives in agentcook-app.',
      },
    },
  },
  tags: ['autodocs'],
};

export default meta;

interface MockPlugin {
  name: string;
  description: string;
  icon: string;
  status: 'ACTIVE' | 'INACTIVE';
}

const PLUGINS: MockPlugin[] = [
  { name: 'GitHub Connector', description: 'Read/write issues, PRs, and repo files via GitHub REST API.', icon: '🐙', status: 'ACTIVE' },
  { name: 'Slack Integration', description: 'Post messages and react to events from Slack workspaces.', icon: '💬', status: 'ACTIVE' },
  { name: 'Model Context Protocol', description: 'Generic MCP-compatible tool server with stdio transport.', icon: '🔌', status: 'ACTIVE' },
  { name: 'Web Search', description: 'Search the public web and return cited snippets.', icon: '🔍', status: 'ACTIVE' },
  { name: 'Legacy API Bridge', description: 'Adapter for deprecated v0 endpoints. Will be removed soon.', icon: '🪝', status: 'INACTIVE' },
];

function badgeStyle(status: MockPlugin['status']): string {
  if (status === 'ACTIVE') {
    return 'background:var(--color-success-50);color:var(--color-success-600);';
  }
  return 'background:var(--color-neutral-100);color:var(--color-neutral-500);';
}

function renderTrigger(selected: MockPlugin | null, open: boolean): HTMLElement {
  const btn = document.createElement('div');
  btn.style.cssText = `
    display: flex;
    align-items: center;
    gap: 8px;
    width: 288px;
    padding: 8px 12px;
    border: 1px solid ${open ? 'var(--color-primary-500)' : 'var(--color-neutral-300)'};
    border-radius: 8px;
    background: white;
    font-family: 'Inter', sans-serif;
    font-size: 14px;
    box-shadow: ${open ? '0 0 0 3px rgba(59,130,246,0.2)' : 'none'};
  `;
  if (selected) {
    btn.innerHTML = `
      <span style="font-size:18px;">${selected.icon}</span>
      <span style="flex:1;font-weight:500;color:var(--color-neutral-900);">${selected.name}</span>
      <span style="padding:2px 6px;border-radius:4px;font-size:11px;${badgeStyle(selected.status)}">${selected.status}</span>
      <span style="color:var(--color-neutral-400);">${open ? '▴' : '▾'}</span>
    `;
  } else {
    btn.innerHTML = `
      <span style="flex:1;color:var(--color-neutral-400);">Select a plugin</span>
      <span style="color:var(--color-neutral-400);">${open ? '▴' : '▾'}</span>
    `;
  }
  return btn;
}

function renderList(selectedIdx: number): HTMLElement {
  const list = document.createElement('div');
  list.style.cssText = `
    margin-top: 4px;
    width: 288px;
    border: 1px solid var(--color-neutral-200);
    border-radius: 8px;
    background: white;
    box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1), 0 4px 6px -4px rgba(0,0,0,0.1);
    padding: 4px 0;
    font-family: 'Inter', sans-serif;
  `;
  PLUGINS.forEach((p, i) => {
    const isSelected = i === selectedIdx;
    const isDisabled = p.status === 'INACTIVE';
    const row = document.createElement('div');
    row.style.cssText = `
      display: flex;
      align-items: flex-start;
      gap: 12px;
      padding: 8px 12px;
      cursor: ${isDisabled ? 'not-allowed' : 'pointer'};
      opacity: ${isDisabled ? '0.5' : '1'};
      background: ${isSelected ? 'var(--color-primary-50)' : 'transparent'};
    `;
    row.innerHTML = `
      <span style="font-size:20px;margin-top:2px;">${p.icon}</span>
      <div style="flex:1;min-width:0;">
        <div style="display:flex;align-items:center;gap:8px;">
          <span style="font-size:14px;font-weight:500;color:var(--color-neutral-900);">${p.name}</span>
          <span style="padding:2px 6px;border-radius:4px;font-size:10px;${badgeStyle(p.status)}">${p.status}</span>
        </div>
        <div style="font-size:12px;color:var(--color-neutral-500);margin-top:2px;line-height:1.4;">${p.description}</div>
      </div>
      ${isSelected ? `<span style="color:var(--color-primary-600);margin-top:2px;">✓</span>` : ''}
    `;
    list.appendChild(row);
  });
  return list;
}

export const Open: StoryObj = {
  name: 'Open (5 plugins, 1 inactive)',
  render: () => {
    const wrap = document.createElement('div');
    wrap.appendChild(renderTrigger(PLUGINS[0], true));
    wrap.appendChild(renderList(0));
    return wrap;
  },
};

export const Closed: StoryObj = {
  name: 'Closed (collapsed trigger)',
  render: () => {
    const wrap = document.createElement('div');
    wrap.appendChild(renderTrigger(PLUGINS[2], false));
    return wrap;
  },
};

export const Empty: StoryObj = {
  name: 'Empty (no selection)',
  render: () => {
    const wrap = document.createElement('div');
    wrap.appendChild(renderTrigger(null, false));
    return wrap;
  },
};
