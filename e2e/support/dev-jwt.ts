/**
 * Mint an HS256 access token the local runtime accepts.
 *
 * Uses the shared development secret (identical default in agentcook-java
 * and the Python runtime), so e2e specs can act as a signed-in user
 * without driving the Java login flow. Never valid in production, where
 * the runtime refuses to start with this secret.
 */
import { createHmac } from "node:crypto";

const DEV_SECRET = process.env.AGENTCOOK_JWT_SECRET ?? "phase3-dev-secret-not-for-prod-32bytes!!";

function b64url(input: Buffer | string): string {
  return Buffer.from(input).toString("base64").replace(/=+$/, "").replace(/\+/g, "-").replace(/\//g, "_");
}

export function devJwt(sub = "e2e-user", ttlSeconds = 3600): string {
  const header = b64url(JSON.stringify({ alg: "HS256", typ: "JWT" }));
  const payload = b64url(
    JSON.stringify({ sub, scope: "agent:read agent:write", exp: Math.floor(Date.now() / 1000) + ttlSeconds }),
  );
  const signature = b64url(createHmac("sha256", DEV_SECRET).update(`${header}.${payload}`).digest());
  return `${header}.${payload}.${signature}`;
}
