/**
 * Cloudflare Worker — Rate Limit (per-user + per-IP)
 *
 * 部署:wrangler deploy
 * 入口:任意请求(本 Worker 用作 reverse proxy 前置 / Cloudflare Route 拦截特定 path)
 * 实现:Cloudflare KV 存窗口计数(per-user 60/min + per-IP 200/min)
 *
 * Phase 5 backlog #11 / draft-cloudflare-turnstile-rate-limit-design.md §2.3
 *
 * 双维度阈值理由(详 design doc §2.3.2):
 *   - per-user(JWT sub):60 req/min(Day 50 baseline 单用户 ~20/min × 3 headroom)
 *   - per-IP:200 req/min(防办公室共享 IP / Cloudflare 边缘已有整站层,这是应用层兜底)
 *
 * 三层防御(design doc §2.3.1)互补:
 *   - 边缘 Cloudflare WAF:整站 200/IP/min(Dashboard 配,不在本 Worker)
 *   - 本 Worker / Traefik 应用层:per-user + per-IP
 *   - ADR-018 业务层:per-account 配额(A Day 56 quota.py 已落)
 */

export interface Env {
  // KV namespace 存计数(每个 key 60s TTL,key = `<scope>:<id>:<window-id>`)
  RATE_LIMIT_KV: KVNamespace;

  // 阈值(可调,wrangler.toml [vars] 注入)
  RATE_LIMIT_PER_USER_PER_MIN?: string; // 默认 60
  RATE_LIMIT_PER_IP_PER_MIN?: string; // 默认 200

  // 监控:Worker 自身向 Prometheus push 指标(可选 / Phase 5 后期)
  METRICS_BASIC_AUTH?: string;
}

// 解析 JWT 从 Authorization header(不验签,只取 sub claim)
//
// 这里不验 JWT 真假 — 后端会再验。本 Worker 只是 rate limit 维度,
// 拿 sub 做 key。攻击者伪造 token = 取不到真 sub = fall back 到 IP 维度。
function extractUserId(authHeader: string | null): string | null {
  if (!authHeader || !authHeader.startsWith("Bearer ")) return null;
  const token = authHeader.slice(7).trim();
  const parts = token.split(".");
  if (parts.length !== 3) return null;
  try {
    // base64url decode payload
    const payload = JSON.parse(
      atob(parts[1].replace(/-/g, "+").replace(/_/g, "/")),
    );
    return typeof payload.sub === "string" ? payload.sub : null;
  } catch {
    return null;
  }
}

// 客户端真实 IP — Cloudflare 注入 CF-Connecting-IP header
function extractClientIp(request: Request): string {
  const cfIp = request.headers.get("CF-Connecting-IP");
  if (cfIp) return cfIp;
  // fallback X-Forwarded-For first hop(自托管时用)
  const xff = request.headers.get("X-Forwarded-For");
  if (xff) return xff.split(",")[0].trim();
  return "unknown";
}

// 1 min window:floor(now_seconds / 60)
function currentWindow(): number {
  return Math.floor(Date.now() / 1000 / 60);
}

interface CheckResult {
  allowed: boolean;
  limit: number;
  remaining: number;
  resetAt: number; // unix seconds
  scope: "user" | "ip";
}

// 增加计数 + 返回是否超限
async function checkAndIncrement(
  kv: KVNamespace,
  scope: "user" | "ip",
  id: string,
  limit: number,
): Promise<CheckResult> {
  const window = currentWindow();
  const key = `${scope}:${id}:${window}`;
  const resetAt = (window + 1) * 60; // 当前 window 结束秒

  // KV 不支持原子 increment;读 → 加 1 → 写 + TTL
  // 高并发下有 race(< 1% 误差,可接受 / 真精准用 Durable Object,Phase 6 buffer)
  const currentRaw = await kv.get(key);
  const current = currentRaw ? parseInt(currentRaw, 10) : 0;
  const next = current + 1;

  // TTL 90s(给 1 min 窗口 + 30s buffer 防钟漂)
  await kv.put(key, String(next), { expirationTtl: 90 });

  return {
    allowed: next <= limit,
    limit,
    remaining: Math.max(0, limit - next),
    resetAt,
    scope,
  };
}

const corsHeaders = {
  "Access-Control-Allow-Origin": "*", // prod 锁域名
  "Access-Control-Expose-Headers":
    "X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset, Retry-After",
};

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const userLimit = parseInt(env.RATE_LIMIT_PER_USER_PER_MIN || "60", 10);
    const ipLimit = parseInt(env.RATE_LIMIT_PER_IP_PER_MIN || "200", 10);

    const userId = extractUserId(request.headers.get("Authorization"));
    const ip = extractClientIp(request);

    // 优先 per-user 限速;无 user 则 per-IP
    const checks: CheckResult[] = [];
    if (userId) {
      checks.push(
        await checkAndIncrement(env.RATE_LIMIT_KV, "user", userId, userLimit),
      );
    }
    checks.push(await checkAndIncrement(env.RATE_LIMIT_KV, "ip", ip, ipLimit));

    // 任一维度 deny 则 deny(取最先撞限的)
    const denied = checks.find((c) => !c.allowed);
    if (denied) {
      return new Response(
        JSON.stringify({
          error: "RATE_LIMITED",
          scope: denied.scope,
          limit: denied.limit,
          retryAfterSeconds: denied.resetAt - Math.floor(Date.now() / 1000),
        }),
        {
          status: 429,
          headers: {
            "Content-Type": "application/json",
            "X-RateLimit-Limit": String(denied.limit),
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": String(denied.resetAt),
            "Retry-After": String(
              denied.resetAt - Math.floor(Date.now() / 1000),
            ),
            ...corsHeaders,
          },
        },
      );
    }

    // 通过 — 把限额 header 加到响应,让前端展示"还剩 X 次"
    // 实际 proxy 转发由 Cloudflare Route(*.agentcook.cc/api/*)+ origin server 处理
    // 本 Worker 用作 transparent middleware:fetch 原 origin + 注入 header
    const upstream = await fetch(request);
    const stricterUserCheck = checks.find((c) => c.scope === "user");
    const ipCheck = checks.find((c) => c.scope === "ip")!;
    const display = stricterUserCheck || ipCheck;

    const headers = new Headers(upstream.headers);
    headers.set("X-RateLimit-Limit", String(display.limit));
    headers.set("X-RateLimit-Remaining", String(display.remaining));
    headers.set("X-RateLimit-Reset", String(display.resetAt));
    return new Response(upstream.body, {
      status: upstream.status,
      statusText: upstream.statusText,
      headers,
    });
  },
};
