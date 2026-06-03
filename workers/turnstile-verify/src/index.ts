/**
 * Cloudflare Worker — Turnstile token verifier
 *
 * 部署:wrangler deploy
 * 入口:POST /verify(JSON body 含 `token` + 可选 `remoteIp`)
 * 响应:200(success: true)/ 401(success: false + error 列表)
 *
 * Phase 5 backlog #11 / ADR-016 §5 / draft-cloudflare-turnstile-rate-limit-design.md
 *
 * 主要职责:
 *   1. 接前端 widget 提交的 token + 用户 IP
 *   2. 调 Cloudflare 官方 siteverify endpoint 验证
 *   3. 返回轻量化判定结果给后端(Java login / Python chat)
 *
 * 为什么要 Worker 而不是后端直接验:
 *   - 后端直接验:每次 login/chat 多 1 个出口 HTTPS 调用,延迟 ~100-200ms
 *   - Worker 边缘验:就近执行,延迟 ~30-50ms,且免费 10 万 req/天 够 demo
 *   - Worker 还可在边缘层直接 reject 无效 token,protect 后端
 *
 * 安全:
 *   - secret 从 wrangler secret put 注入,不写代码
 *   - 不记录 token 内容(隐私 + 防日志泄露)
 *   - response 严格 JSON,不返 secret 上下文
 */

export interface Env {
  // wrangler secret put TURNSTILE_SECRET — 真值由作者 Cloudflare Dashboard 创 Turnstile site 后填
  TURNSTILE_SECRET: string;

  // 可选:开发环境 bypass(test secret 1x00000000000000000000AA 由 Cloudflare 提供)
  TURNSTILE_BYPASS?: string; // "true" 字符串
}

interface VerifyRequest {
  token: string;
  remoteIp?: string;
}

interface CloudflareSiteverifyResponse {
  success: boolean;
  challenge_ts?: string;
  hostname?: string;
  error_codes?: string[];
  action?: string;
  cdata?: string;
}

const SITEVERIFY_URL =
  "https://challenges.cloudflare.com/turnstile/v0/siteverify";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*", // prod 应锁 agentcook.cc / staging.agentcook.cc
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
  "Access-Control-Max-Age": "86400",
};

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    // CORS preflight
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: corsHeaders });
    }

    // 路由:只接 POST /verify
    const url = new URL(request.url);
    if (request.method !== "POST" || url.pathname !== "/verify") {
      return jsonResponse({ success: false, error: "NOT_FOUND" }, 404);
    }

    // dev bypass(避免本机断 Cloudflare 时 dev 卡死)
    if (env.TURNSTILE_BYPASS === "true") {
      return jsonResponse({ success: true, bypass: true }, 200);
    }

    // 解析 body
    let body: VerifyRequest;
    try {
      body = await request.json<VerifyRequest>();
    } catch {
      return jsonResponse({ success: false, error: "INVALID_JSON" }, 400);
    }

    if (!body.token || typeof body.token !== "string") {
      return jsonResponse({ success: false, error: "MISSING_TOKEN" }, 400);
    }

    // secret 必须从 env 注入(wrangler secret put TURNSTILE_SECRET)
    if (!env.TURNSTILE_SECRET) {
      return jsonResponse(
        { success: false, error: "WORKER_MISCONFIGURED" },
        500,
      );
    }

    // 用 application/x-www-form-urlencoded 调 Cloudflare(官方推荐 / siteverify 不接 JSON body)
    const formData = new URLSearchParams();
    formData.append("secret", env.TURNSTILE_SECRET);
    formData.append("response", body.token);
    if (body.remoteIp) {
      formData.append("remoteip", body.remoteIp);
    }

    let cfResponse: Response;
    try {
      cfResponse = await fetch(SITEVERIFY_URL, {
        method: "POST",
        body: formData,
        // Cloudflare Worker 自带 timeout ~30s,这里不再设
      });
    } catch (err) {
      // Cloudflare 自身故障 — 不挡用户(R1 缓解 / 详 design doc §5)
      // prod 应根据 SLO 决策:严格(reject)or 宽松(pass + alert)
      // 这里选择 reject,触发 PrometheusRule turnstile-fail-rate alert
      return jsonResponse(
        { success: false, error: "SITEVERIFY_UNREACHABLE" },
        503,
      );
    }

    if (!cfResponse.ok) {
      return jsonResponse(
        { success: false, error: "SITEVERIFY_HTTP_" + cfResponse.status },
        503,
      );
    }

    const result = await cfResponse.json<CloudflareSiteverifyResponse>();

    if (!result.success) {
      // error_codes 见 https://developers.cloudflare.com/turnstile/get-started/server-side-validation/#error-codes
      return jsonResponse(
        {
          success: false,
          error: "VERIFICATION_FAILED",
          error_codes: result.error_codes,
        },
        401,
      );
    }

    // 成功 — 不返 secret 上下文(challenge_ts / hostname 可选返,辅助后端关联)
    return jsonResponse(
      {
        success: true,
        hostname: result.hostname,
        challenge_ts: result.challenge_ts,
      },
      200,
    );
  },
};

function jsonResponse(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json",
      ...corsHeaders,
    },
  });
}
