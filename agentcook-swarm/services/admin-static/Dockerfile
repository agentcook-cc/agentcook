# Stage 1: Build admin (Vue 3 + Vite)
FROM node:20-alpine AS builder
WORKDIR /build

# Install pnpm
RUN corepack enable && corepack prepare pnpm@9 --activate

# Copy workspace root config for monorepo resolution
COPY agentcook-cc/package.json agentcook-cc/pnpm-workspace.yaml agentcook-cc/pnpm-lock.yaml ./
COPY agentcook-cc/agentcook-admin/package.json ./agentcook-admin/
COPY agentcook-cc/agentcook-design-tokens/package.json ./agentcook-design-tokens/

# Install dependencies
RUN pnpm install --frozen-lockfile --filter @agentcook-cc/admin...

# Copy source
COPY agentcook-cc/agentcook-admin ./agentcook-admin
COPY agentcook-cc/agentcook-design-tokens ./agentcook-design-tokens

# Build
WORKDIR /build/agentcook-admin
RUN pnpm build

# Stage 2: Serve with nginx
FROM nginx:1.27-alpine
COPY --from=builder /build/agentcook-admin/dist /usr/share/nginx/html
COPY agentcook-cc/agentcook-swarm/services/admin-static/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
