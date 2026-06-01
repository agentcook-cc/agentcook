# Quickstart — 5 minutes to first agent reply

Assumes you've completed [Installation](/guide/installation) and both the
Python (`:8000`) and Java (`:8080`) services are up.

## 1. Create a user

```bash
curl -X POST localhost:8080/api/v1/users \
  -H "Content-Type: application/json" \
  -d '{"email":"alice@example.com","nickname":"Alice"}'
```

The response contains a `UserResponse` with a UUID — keep it handy.

## 2. Authenticate (dev profile)

```bash
TOKEN=$(curl -s -X POST localhost:8080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","password":"dev"}' | jq -r '.accessToken')
echo "Bearer $TOKEN"
```

The dev profile returns a stable dummy token. Production swaps to OAuth2
Resource Server with JWT validation — see
[Java REST reference](/reference/java-rest).

## 3. Open a session

```bash
SESSION=$(curl -s -X POST localhost:8080/api/v1/sessions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"userId":"<USER_UUID>","title":"first chat"}' | jq -r '.id')
```

## 4. Send your first message (streamed)

Chat is served by the Python runtime via Server-Sent Events:

```bash
curl -N -X POST localhost:8000/api/v1/agent/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"sessionId\":\"$SESSION\",\"message\":\"hello agentcook\"}"
```

You should see SSE chunks streaming back — each `data:` line carries a
partial reply token. The stream ends with `data: [DONE]`.

## 5. Open the admin UI

```bash
pnpm --filter @agentcook-cc/admin dev
# → http://localhost:5174
```

Log in with `alice / dev`. You'll see the user you created in
**Users**, the session in **Sessions**, and the live LLM trace under
**Monitoring → Traces** (Jaeger).

## What's next?

- Build your own tool: [Your First Plugin](/guide/first-plugin)
- Wire a custom model: [Python SDK](/reference/python-sdk)
- See the architectural decisions: [ADR index](/adr/)
