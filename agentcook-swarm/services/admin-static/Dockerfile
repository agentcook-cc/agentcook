# Static build of agentcook-admin served by nginx under /admin/ behind the swarm gateway.
# Build from the repository root:
#   docker build -f agentcook-swarm/services/admin-static/Dockerfile .

FROM node:20-alpine AS builder
WORKDIR /build
RUN corepack enable && corepack prepare pnpm@9.12.0 --activate
ENV SKIP_SIMPLE_GIT_HOOKS=1

# Workspace manifests first so the dependency layer caches.
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml .npmrc ./
COPY agentcook-admin/package.json ./agentcook-admin/
COPY agentcook-design-tokens/package.json ./agentcook-design-tokens/
RUN pnpm install --frozen-lockfile --filter @agentcook-cc/admin...

COPY tsconfig.base.json ./
COPY agentcook-design-tokens ./agentcook-design-tokens
COPY agentcook-admin ./agentcook-admin
RUN pnpm --filter @agentcook-cc/design-tokens build \
    && VITE_BASE_PATH=/admin/ pnpm --filter @agentcook-cc/admin build

FROM nginx:1.27-alpine
COPY --from=builder /build/agentcook-admin/dist /usr/share/nginx/html
COPY agentcook-swarm/services/admin-static/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
