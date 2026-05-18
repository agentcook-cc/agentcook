export interface MenuItem {
  path: string;
  title: string;
  icon: string;
  roles?: string[];
  children?: MenuItem[];
}

/**
 * 侧边栏菜单配置。Phase 3 Day 26-32 逐步填充真实页面。
 * icon 字段对应 @element-plus/icons-vue 已全局注册的组件名。
 * roles 为空表示所有角色可见；Phase 3 实现 RBAC 时按 roles 过滤。
 */
export const menuConfig: MenuItem[] = [
  {
    path: "/dashboard",
    title: "Dashboard",
    icon: "Monitor",
  },
  {
    path: "/agents",
    title: "Agents",
    icon: "Cpu",
    children: [
      { path: "/agents/list", title: "Agent List", icon: "List" },
      { path: "/agents/memory", title: "Memory Browser", icon: "Notebook" },
    ],
  },
  {
    path: "/skills",
    title: "Skills",
    icon: "MagicStick",
  },
  {
    path: "/plugins",
    title: "Plugins",
    icon: "Connection",
  },
  {
    path: "/connectors",
    title: "Connectors",
    icon: "Link",
  },
  {
    path: "/users",
    title: "Users & Roles",
    icon: "User",
    roles: ["admin"],
  },
  {
    path: "/monitoring",
    title: "Monitoring",
    icon: "DataLine",
    roles: ["admin"],
  },
];
