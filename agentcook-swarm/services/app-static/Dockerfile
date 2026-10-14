# Static build of agentcook-app served by nginx under /app/ behind the swarm gateway.
# Build from the repository root:
#   docker build -f agentcook-swarm/services/app-static/Dockerfile .

FROM node:20-alpine AS builder
WORKDIR /build
RUN corepack enable && corepack prepare pnpm@9.12.0 --activate
ENV SKIP_SIMPLE_GIT_HOOKS=1

# Workspace manifests first so the dependency layer caches.
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml .npmrc ./
COPY agentcook-app/package.json ./agentcook-app/
COPY agentcook-design-tokens/package.json ./agentcook-design-tokens/
RUN pnpm install --frozen-lockfile --filter @agentcook-cc/app...

COPY tsconfig.base.json ./
COPY agentcook-design-tokens ./agentcook-design-tokens
COPY agentcook-app ./agentcook-app
RUN pnpm --filter @agentcook-cc/design-tokens build \
    && VITE_BASE_PATH=/app/ pnpm --filter @agentcook-cc/app build

FROM nginx:1.27-alpine
COPY --from=builder /build/agentcook-app/dist /usr/share/nginx/html
COPY agentcook-swarm/services/app-static/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
