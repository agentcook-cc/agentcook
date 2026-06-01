import type { Meta, StoryObj } from '@storybook/html';

const meta: Meta = {
  title: 'Components/PluginListView',
  parameters: {
    layout: 'fullscreen',
    docs: {
      description: {
        component:
          'Visual mock of `admin/src/views/PluginListView.vue` — proves the ProTable + status tag + action button palette read from tokens. Real component lives in agentcook-admin (Vue 3 + Element Plus).',
      },
    },
  },
  tags: ['autodocs'],
};

export default meta;

type Status = 'PUBLISHED' | 'DRAFT' | 'DISABLED';
type Kind = 'MCP' | 'HTTP' | 'OAUTH' | 'WEBHOOK';

interface Row {
  name: string;
  version: string;
  kind: Kind;
  status: Status;
  updatedAt: string;
}

const ROWS: Row[] = [
  { name: 'GitHub Connector', version: '1.2.0', kind: 'HTTP', status: 'PUBLISHED', updatedAt: '2026-05-15 10:30' },
  { name: 'Slack Integration', version: '2.0.1', kind: 'WEBHOOK', status: 'PUBLISHED', updatedAt: '2026-05-14 14:20' },
  { name: 'OAuth2 Provider', version: '0.9.0', kind: 'OAUTH', status: 'DRAFT', updatedAt: '2026-05-13 09:15' },
  { name: 'Model Context Protocol', version: '1.0.0', kind: 'MCP', status: 'PUBLISHED', updatedAt: '2026-05-12 16:45' },
  { name: 'Legacy API Bridge', version: '0.5.3', kind: 'HTTP', status: 'DISABLED', updatedAt: '2026-05-10 11:00' },
  { name: 'Custom Webhook Handler', version: '1.1.0', kind: 'WEBHOOK', status: 'DRAFT', updatedAt: '2026-05-08 13:30' },
  { name: 'Advanced MCP Server', version: '0.3.0', kind: 'MCP', status: 'DRAFT', updatedAt: '2026-05-05 08:00' },
  { name: 'Web Search', version: '1.0.4', kind: 'HTTP', status: 'PUBLISHED', updatedAt: '2026-05-03 17:20' },
];

const STATUS_TAG: Record<Status, { bg: string; fg: string; border: string }> = {
  PUBLISHED: {
    bg: 'var(--color-success-50)',
    fg: 'var(--color-success-600)',
    border: 'var(--color-success-500)',
  },
  DRAFT: {
    bg: 'var(--color-info-50)',
    fg: 'var(--color-info-600)',
    border: 'var(--color-info-500)',
  },
  DISABLED: {
    bg: 'var(--color-warning-50)',
    fg: 'var(--color-warning-600)',
    border: 'var(--color-warning-500)',
  },
};

function statusTag(status: Status): string {
  const t = STATUS_TAG[status];
  return `<span style="display:inline-block;padding:2px 8px;border-radius:4px;background:${t.bg};color:${t.fg};border:1px solid ${t.border};font-size:11px;font-weight:500;">${status}</span>`;
}

function kindTag(kind: Kind): string {
  return `<span style="display:inline-block;padding:2px 8px;border-radius:4px;background:white;color:var(--color-neutral-600);border:1px solid var(--color-neutral-300);font-size:11px;">${kind}</span>`;
}

function actionLink(label: string, color: string): string {
  return `<a style="color:${color};font-size:12px;margin-right:8px;cursor:pointer;text-decoration:none;">${label}</a>`;
}

function renderActions(status: Status): string {
  const detail = actionLink('Detail', 'var(--color-primary-600)');
  const enable = actionLink('Enable', 'var(--color-success-600)');
  const disable = actionLink('Disable', 'var(--color-warning-600)');
  if (status === 'PUBLISHED') return detail + disable;
  if (status === 'DISABLED' || status === 'DRAFT') return detail + enable;
  return detail;
}

export const FullPage: StoryObj = {
  name: 'Full Page (8 mock rows)',
  render: () => {
    const wrap = document.createElement('div');
    wrap.style.cssText = `
      padding: 24px;
      background: var(--color-neutral-50);
      font-family: 'Inter', -apple-system, sans-serif;
      min-height: 100vh;
    `;

    const header = `
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
        <h2 style="margin:0;font-size:20px;font-weight:600;color:var(--color-neutral-900);">Plugin Management</h2>
        <button style="padding:8px 16px;background:var(--color-primary-500);color:white;border:0;border-radius:6px;font-size:14px;font-weight:500;cursor:pointer;">Create Plugin</button>
      </div>
    `;

    const searchBar = `
      <div style="display:flex;align-items:center;margin-bottom:16px;gap:12px;">
        <input placeholder="Search by name..." style="width:320px;padding:8px 12px;border:1px solid var(--color-neutral-300);border-radius:6px;font-size:14px;" />
        <select style="width:150px;padding:8px 12px;border:1px solid var(--color-neutral-300);border-radius:6px;font-size:14px;">
          <option>Status</option><option>Published</option><option>Draft</option><option>Disabled</option>
        </select>
        <select style="width:130px;padding:8px 12px;border:1px solid var(--color-neutral-300);border-radius:6px;font-size:14px;">
          <option>Kind</option><option>MCP</option><option>HTTP</option><option>OAUTH</option><option>WEBHOOK</option>
        </select>
      </div>
    `;

    const tableHead = `
      <thead>
        <tr style="background:var(--color-neutral-100);text-align:left;font-size:12px;font-weight:600;color:var(--color-neutral-600);text-transform:uppercase;letter-spacing:0.04em;">
          <th style="padding:10px 12px;">Name</th>
          <th style="padding:10px 12px;">Version</th>
          <th style="padding:10px 12px;">Kind</th>
          <th style="padding:10px 12px;">Status</th>
          <th style="padding:10px 12px;">Updated At</th>
          <th style="padding:10px 12px;">Actions</th>
        </tr>
      </thead>
    `;

    const tableBody = `
      <tbody>
        ${ROWS.map(
          (r) => `
            <tr style="border-top:1px solid var(--color-neutral-200);background:white;font-size:14px;color:var(--color-neutral-800);">
              <td style="padding:10px 12px;font-weight:500;color:var(--color-neutral-900);">${r.name}</td>
              <td style="padding:10px 12px;">${r.version}</td>
              <td style="padding:10px 12px;">${kindTag(r.kind)}</td>
              <td style="padding:10px 12px;">${statusTag(r.status)}</td>
              <td style="padding:10px 12px;color:var(--color-neutral-500);font-size:13px;">${r.updatedAt}</td>
              <td style="padding:10px 12px;">${renderActions(r.status)}</td>
            </tr>
          `,
        ).join('')}
      </tbody>
    `;

    wrap.innerHTML = `
      ${header}
      ${searchBar}
      <div style="background:white;border:1px solid var(--color-neutral-200);border-radius:8px;overflow:hidden;box-shadow:0 1px 2px rgba(0,0,0,0.05);">
        <table style="width:100%;border-collapse:collapse;">
          ${tableHead}
          ${tableBody}
        </table>
      </div>
    `;
    return wrap;
  },
};

export const StatusTags: StoryObj = {
  name: 'Status Tag Palette',
  render: () => {
    const wrap = document.createElement('div');
    wrap.style.cssText = "font-family: 'Inter', sans-serif; display: flex; flex-direction: column; gap: 12px;";
    (['PUBLISHED', 'DRAFT', 'DISABLED'] as Status[]).forEach((s) => {
      const row = document.createElement('div');
      row.style.cssText = 'display:flex;align-items:center;gap:12px;';
      row.innerHTML = `
        ${statusTag(s)}
        <code style="font-family:'JetBrains Mono',monospace;font-size:12px;color:var(--color-neutral-500);">${s} → ${
          s === 'PUBLISHED' ? 'success' : s === 'DRAFT' ? 'info' : 'warning'
        } palette</code>
      `;
      wrap.appendChild(row);
    });
    return wrap;
  },
};
