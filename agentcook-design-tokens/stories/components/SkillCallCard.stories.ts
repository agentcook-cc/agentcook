import type { Meta, StoryObj } from '@storybook/html';

const meta: Meta = {
  title: 'Components/SkillCallCard',
  parameters: {
    layout: 'padded',
    docs: {
      description: {
        component:
          'Visual mock of `app/src/components/SkillCallCard.tsx` rendered with raw HTML + design tokens — proves the 3 status states (pending / success / error) read correctly from the token palette. Real component lives in agentcook-app and consumes Tailwind classes; this story validates the underlying tokens those classes resolve to.',
      },
    },
  },
  tags: ['autodocs'],
};

export default meta;

interface MockCall {
  name: string;
  status: 'pending' | 'success' | 'error';
  duration: string;
  input: string;
  output?: string;
  error?: string;
}

const STATE_TOKENS = {
  pending: {
    border: 'var(--color-neutral-300)',
    badgeBg: 'var(--color-neutral-100)',
    badgeFg: 'var(--color-neutral-700)',
    label: 'Running',
  },
  success: {
    border: 'var(--color-success-50)',
    badgeBg: 'var(--color-success-50)',
    badgeFg: 'var(--color-success-600)',
    label: 'Success',
  },
  error: {
    border: 'var(--color-danger-500)',
    badgeBg: 'var(--color-danger-50)',
    badgeFg: 'var(--color-danger-600)',
    label: 'Failed',
  },
} as const;

function renderCard(call: MockCall, expanded: boolean): HTMLElement {
  const tone = STATE_TOKENS[call.status];
  const card = document.createElement('div');
  card.style.cssText = `
    border: 2px solid ${tone.border};
    border-radius: 8px;
    background: white;
    box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    margin-bottom: 12px;
    font-family: 'Inter', -apple-system, sans-serif;
  `;

  const header = document.createElement('div');
  header.style.cssText = `
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 8px 12px;
  `;
  const icon =
    call.status === 'pending'
      ? '⏳'
      : call.status === 'success'
        ? '✓'
        : '✕';
  header.innerHTML = `
    <span style="display:inline-flex;align-items:center;justify-content:center;width:24px;height:24px;border-radius:9999px;background:${tone.badgeBg};color:${tone.badgeFg};font-weight:700;font-size:12px;">${icon}</span>
    <span style="flex:1;font-size:14px;font-weight:500;color:var(--color-neutral-900);">${call.name}</span>
    <span style="padding:2px 6px;border-radius:4px;background:${tone.badgeBg};color:${tone.badgeFg};font-size:11px;">${tone.label}</span>
    <span style="font-size:12px;color:var(--color-neutral-500);">${call.duration}</span>
    <span style="color:var(--color-neutral-400);">${expanded ? '▾' : '▸'}</span>
  `;
  card.appendChild(header);

  if (expanded) {
    const body = document.createElement('div');
    body.style.cssText = `
      border-top: 1px solid var(--color-neutral-100);
      padding: 8px 12px;
      font-size: 12px;
    `;
    body.innerHTML = `
      <div style="margin-bottom:8px;">
        <div style="font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.04em;color:var(--color-neutral-500);margin-bottom:4px;">Input</div>
        <pre style="background:var(--color-neutral-50);padding:8px;border-radius:4px;font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--color-neutral-800);margin:0;overflow-x:auto;">${call.input}</pre>
      </div>
      ${
        call.output
          ? `<div>
              <div style="font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.04em;color:var(--color-neutral-500);margin-bottom:4px;">Output</div>
              <pre style="background:var(--color-neutral-50);padding:8px;border-radius:4px;font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--color-neutral-800);margin:0;overflow-x:auto;">${call.output}</pre>
            </div>`
          : ''
      }
      ${
        call.error
          ? `<div>
              <div style="font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.04em;color:var(--color-danger-600);margin-bottom:4px;">Error</div>
              <pre style="background:var(--color-danger-50);padding:8px;border-radius:4px;font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--color-danger-600);margin:0;overflow-x:auto;">${call.error}</pre>
            </div>`
          : ''
      }
      ${
        call.status === 'pending'
          ? `<div style="font-size:11px;font-style:italic;color:var(--color-neutral-500);">Waiting for tool response…</div>`
          : ''
      }
    `;
    card.appendChild(body);
  }
  return card;
}

export const ThreeStates: StoryObj = {
  name: '3 States (pending / success / error)',
  render: () => {
    const wrap = document.createElement('div');
    wrap.style.cssText = 'max-width: 640px;';
    [
      renderCard(
        {
          name: 'web_search',
          status: 'pending',
          duration: '—',
          input: '{ "query": "latest LLM benchmarks" }',
        },
        true,
      ),
      renderCard(
        {
          name: 'github.read_file',
          status: 'success',
          duration: '342ms',
          input: '{ "owner": "agentcook-cc", "repo": "agentcook", "path": "README.md" }',
          output: '"# AgentCook\\n\\nProduction-grade AI agent harness…"',
        },
        true,
      ),
      renderCard(
        {
          name: 'shell.run',
          status: 'error',
          duration: '1.20s',
          input: '{ "command": "rm -rf /protected" }',
          error: 'PermissionDenied: path is on the host-write redline',
        },
        true,
      ),
    ].forEach((el) => wrap.appendChild(el));
    return wrap;
  },
};

export const Collapsed: StoryObj = {
  name: 'Collapsed (header only)',
  render: () => {
    const wrap = document.createElement('div');
    wrap.style.cssText = 'max-width: 640px;';
    [
      renderCard(
        {
          name: 'web_search',
          status: 'success',
          duration: '210ms',
          input: '{}',
          output: '[…]',
        },
        false,
      ),
      renderCard(
        {
          name: 'shell.run',
          status: 'error',
          duration: '1.20s',
          input: '{}',
          error: 'PermissionDenied',
        },
        false,
      ),
    ].forEach((el) => wrap.appendChild(el));
    return wrap;
  },
};
