# Your First Plugin

A plugin extends the agent with a new tool. agentcook plugins are zip
bundles containing a `plugin.json` manifest and an entrypoint — they run
inside an isolated Docker sandbox so a buggy or hostile tool can't reach
the host.

This walkthrough builds a `hello-echo` plugin that echoes its input back.

## 1. Scaffold

```bash
mkdir hello-echo && cd hello-echo
```

Create `plugin.json`:

```json
{
  "name": "hello-echo",
  "version": "0.1.0",
  "kind": "HTTP",
  "description": "Echoes the input back — sanity check for plugin scaffolding.",
  "permissions": ["net:none"],
  "entry": {
    "command": "python",
    "args": ["server.py"]
  }
}
```

Schema rules:

- `name`: lower-kebab-case, unique per registry
- `version`: SemVer
- `kind`: `MCP` | `HTTP` | `OAUTH` | `WEBHOOK`
- `permissions`: capability scopes, format `domain:action`

## 2. Write the entrypoint

`server.py`:

```python
from http.server import BaseHTTPRequestHandler, HTTPServer
import json

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers["Content-Length"])
        body = json.loads(self.rfile.read(length))
        reply = {"echo": body.get("message", "")}
        out = json.dumps(reply).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

HTTPServer(("0.0.0.0", 8000), Handler).serve_forever()
```

## 3. Bundle

```bash
cd ..
zip -r hello-echo.zip hello-echo/
```

## 4. Upload through the admin

1. Open `http://localhost:5174/plugins`
2. Click **Create Plugin**, drag-and-drop `hello-echo.zip`
3. Wait for upload + validation (the admin runs the manifest through
   ajv against `agent-plugin-spec` before submitting)
4. Click **Enable** on the new row

## 5. Use it from chat

In `agentcook-app` (`http://localhost:5173`), open the plugin selector at
the bottom of the composer and pick **hello-echo**. Send a message — the
agent will route the message through your plugin's `/echo` endpoint.

The sandbox runner enforces the permissions you declared: `net:none`
blocks outbound HTTP. Try declaring `["net:fetch"]` and writing a tool
that talks to a public API — the sandbox will let it through, while still
blocking host filesystem and inter-container traffic.

## Where to go next

- Inspect the manifest schema details: [`agent-plugin-spec` repository](https://github.com/agentcook-cc/agent-plugin-spec)
- Read the sandbox security model: [ADR-004](/adr/)
- Browse built-in plugins under `agentcook-cc/poc/plugin-sandbox/`
