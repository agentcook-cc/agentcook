---
layout: home

hero:
  name: agentcook
  text: Production-grade AI agent framework
  tagline: Python core · Java business backend · TypeScript UI — everything you need to ship a real agent product.
  actions:
    - theme: brand
      text: Get Started
      link: /guide/installation
    - theme: alt
      text: View on GitHub
      link: https://github.com/agentcook-cc/agentcook

features:
  - icon: 🧠
    title: 9-dimension Harness
    details: Memory · Tools · Context · Sandbox · Hooks · Routing · Telemetry · Compaction · Pruning — every dimension of a long-running agent, covered.
  - icon: 🌐
    title: Bilingual Backend
    details: Python runtime for agent core (FastAPI + asyncio) plus Java business layer (Spring Boot + DDD) — pick the right tool per concern.
  - icon: 🔌
    title: Plugin Sandbox
    details: Docker-based isolation for third-party tools. 5 attack-vector tests baked in. Capability-driven permission model.
  - icon: 📊
    title: First-class Observability
    details: OpenTelemetry traces, Prometheus metrics, Langfuse LLM telemetry, structured JSON logs — wired from day one.
  - icon: 🎨
    title: Shared Design Tokens
    details: Single source-of-truth for color, type, spacing — both admin (Vue 3) and chat app (React 19) consume the same tokens.
  - icon: 🚀
    title: K8s + Helm Ready
    details: Helm chart, blue/green workflow, multi-arch Docker images, Cloudflare Pages for the static surfaces.
---

## What is agentcook?

agentcook is an opinionated **agent harness** that pulls together the moving
parts every production agent needs — memory, tools, context management,
sandbox isolation, hook pipelines, multi-model routing — behind a coherent
API.

It is split across three runtimes by concern:

- **Python core** (`agentcook-core` + `agentcook` FastAPI): the agent loop,
  memory layers, plugin runtime, model routing, observability.
- **Java business backend** (`agentcook-java`): users, sessions, plugins,
  connectors, permissions — the operational data plane.
- **TypeScript front-ends** (`agentcook-admin` Vue 3 + `agentcook-app`
  React 19 + Electron): admin dashboard and the end-user chat surface.

A Traefik gateway fans traffic between Python and Java, and a Helm chart
deploys the lot to Kubernetes.

## 5-minute path

```bash
git clone https://github.com/agentcook-cc/agentcook
cd agentcook-cc
make dev          # docker-compose: postgres, redis, jaeger, prometheus
uv sync           # python deps
uv run uvicorn agentcook_app.main:app --reload
```

Open `http://localhost:8000/docs` for the live OpenAPI explorer. Continue
with the [Quickstart](/guide/quickstart) to send your first chat request.
