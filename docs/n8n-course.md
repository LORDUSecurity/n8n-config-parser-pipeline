# n8n from Zero to Production: A Real-World Course

> *A deep-dive into building a file-processing pipeline with n8n, Docker, and Python — born from a real production system.*

---

## Table of Contents

1. [The Problem We're Solving](#1-the-problem-were-solving)
2. [Why Not Just a Python Script?](#2-why-not-just-a-python-script)
3. [Why Docker?](#3-why-docker)
4. [Why Docker Compose + Dockerfile (Not Just One)](#4-why-docker-compose--dockerfile-not-just-one)
5. [n8n Core Concepts](#5-n8n-core-concepts)
6. [Our Pipeline Architecture](#6-our-pipeline-architecture)
7. [The Dockerfile — Extending n8n with Python](#7-the-dockerfile--extending-n8n-with-python)
8. [The docker-compose.yml — Wiring It All Together](#8-the-docker-composeyml--wiring-it-all-together)
9. [The Workflow — Node by Node](#9-the-workflow--node-by-node)
10. [Binary Data in n8n — The Big Gotcha](#10-binary-data-in-n8n--the-big-gotcha)
11. [The Code Node Sandbox — What You Can and Cannot Do](#11-the-code-node-sandbox--what-you-can-and-cannot-do)
12. [Volume Mounts — The Silent Directory Killer](#12-volume-mounts--the-silent-directory-killer)
13. [The Webhook + Respond Pattern — Closing the HTTP Loop](#13-the-webhook--respond-pattern--closing-the-http-loop)
14. [All the Bugs We Hit (So You Don't Have To)](#14-all-the-bugs-we-hit-so-you-dont-have-to)
15. [Quick Reference Cheat Sheet](#15-quick-reference-cheat-sheet)

---

## 1. The Problem We're Solving

An operator manages **100+ distributed devices** across multiple sites. Each device produces a text-based configuration dump (settings, policies, interface descriptions, metadata…). Engineers need all these configs consolidated into a single styled Excel workbook for audit and planning.

The manual process:
1. Collect config files from engineers (`.txt`, `.log`, switch IP dumps)
2. Read each file, extract ports/VLANs/services
3. Cross-reference with port-switch verification files
4. Build a formatted Excel workbook

This is tedious, error-prone, and doesn't scale. We need automation.

**The catch:** The parsing logic is complex Python (1800+ lines of regex-heavy network config parsing). The trigger is an HTTP file upload. The output is a downloadable Excel file. We need a pipeline that glues all of this together.

---

## 2. Why Not Just a Python Script?

You *could* write a single Python script that does everything. But consider:

| Concern | Pure Python | n8n + Python |
|---------|-------------|--------------|
| HTTP endpoint | You need Flask/FastAPI + CORS + auth | One Webhook node |
| File upload handling | Multipart parsing, temp files | Built-in binary data management |
| Pipeline orchestration | Manual error handling, logging | Visual flow, per-node error tracking |
| Re-triggering | Cron + custom code | One click or webhook call |
| Monitoring | You build it | Built-in execution history |
| Modifying the flow | Edit code, test, deploy | Drag-and-drop in browser |

n8n gives us the **HTTP layer, orchestration, and monitoring** for free. Python handles what it's best at: **heavy data processing**.

---

## 3. Why Docker?

### The Environment Problem

Our parser needs:
- Python 3.12+ with `openpyxl`
- A specific filesystem layout (`/data/inbox`, `/data/staging`, `/data/out`)
- n8n itself (Node.js application)

On your Windows machine, you'd need to install Python, pip, openpyxl, Node.js, n8n, configure paths… On a server, you'd need the same. Docker solves this:

```
One command → reproducible environment everywhere
```

### Why Not Just the Official n8n Image?

The official `n8n` image does NOT include Python. Our pipeline needs Python scripts to run *inside* the same container as n8n (because the Execute Command nodes run shell commands locally). So we need to **extend** the official image.

This is where the Dockerfile comes in.

---

## 4. Why Docker Compose + Dockerfile (Not Just One)?

They serve different purposes:

### Dockerfile = "What's inside the image"

The Dockerfile defines the **container image**: what software is installed, what files are baked in, what user runs the app.

```dockerfile
FROM docker.n8n.io/n8nio/n8n:2.0.2    # Start from official n8n
RUN apk add python3 py3-pip             # Add Python
RUN pip install openpyxl                # Add Excel library
COPY parse_configs.py /opt/scripts/     # Bake in our parser
```

This image is **portable** — you can push it to a registry, deploy it anywhere.

### docker-compose.yml = "How to run the container"

Compose defines the **runtime configuration**: ports, volumes, environment variables, restart policy.

```yaml
services:
  n8n:
    build:
      context: ../..                    # Where to find the Dockerfile
      dockerfile: n8n_chain/n8n/Dockerfile
    ports:
      - "5678:5678"                     # Expose n8n web UI
    volumes:
      - ../../n8n_data:/data            # Share files with host
    environment:
      NODE_FUNCTION_ALLOW_BUILTIN: fs,path  # Let Code nodes use fs
```

### Why Both?

| Concern | Dockerfile | docker-compose.yml |
|---------|-----------|-------------------|
| Install Python | ✅ | |
| Copy parser scripts | ✅ | |
| Map port 5678 | | ✅ |
| Mount shared volume | | ✅ |
| Set environment vars | | ✅ |
| Restart policy | | ✅ |
| Build once, run many ways | ✅ | ✅ |

**Rule of thumb:** If it changes the *image contents*, put it in the Dockerfile. If it changes *how the container runs*, put it in docker-compose.yml.

### Why Not `docker run` Commands?

You *could* do:
```bash
docker build -t my-n8n -f n8n_chain/n8n/Dockerfile .
docker run -p 5678:5678 -v ./n8n_data:/data -e NODE_FUNCTION_ALLOW_BUILTIN=fs,path my-n8n
```

But compose gives you:
- **One command** (`docker compose up -d`) instead of memorizing flags
- **Declarative** configuration (checked into git, reproducible)
- **Named volumes** (`n8n_home:`) for persistent data
- **Easy rebuild** (`docker compose up --build -d`)

---

## 5. n8n Core Concepts

### What Is n8n?

n8n is a **workflow automation engine**. You build flows by connecting nodes. Each node does one thing. Data flows from left to right.

```
[Trigger] → [Transform] → [Action] → [Respond]
```

### Key Concepts

**Workflow** — A JSON document describing nodes + connections. Importable, exportable, versionable.

**Node** — A single step in the workflow. Types we use:
- **Webhook** — Receives HTTP requests (our trigger)
- **Code** — Runs JavaScript in a sandbox
- **Execute Command** — Runs a shell command (Python scripts)
- **Respond to Webhook** — Sends the HTTP response back

**Connection** — Wires between nodes. Data flows through connections. Defined in the `connections` section of the workflow JSON:

```json
"connections": {
  "Webhook: receive configs": {
    "main": [[{"node": "Save uploads to inbox", "type": "main", "index": 0}]]
  }
}
```

**Item** — The unit of data flowing through the workflow. Each item has:
- `json` — A JSON object (your data)
- `binary` — Optional binary data (file uploads)

**Execution** — One run of the workflow. n8n logs every execution with input/output per node. You can inspect, retry, or debug individual executions.

### The Execution Model

```
Webhook receives POST
    │
    ▼
┌─────────────────────────┐
│  Item 1: {binary: file1} │──→ Code: save to disk
│  Item 2: {binary: file2} │         │
│  Item 3: {binary: file3} │         ▼
└─────────────────────────┘   Execute Command: python3 01_normalize.py
                                       │
                                       ▼
                              Execute Command: python3 02_parse.py
                                       │
                                       ▼
                              Execute Command: python3 03_generate_xlsx.py
                                       │
                                       ▼
                              Code: read xlsx, attach as binary
                                       │
                                       ▼
                              Respond to Webhook: send xlsx back
```

All items flow together through the Execute Command nodes (the Python scripts ignore the item structure and just process files on disk).

---

## 6. Our Pipeline Architecture

```
                    curl -F "file=@config.txt" http://host:5678/webhook/rax-integration
                                              │
    ┌─────────────────────────────────────────┘
    ▼
┌──────────────────────┐
│  1. Webhook           │  Receives multipart file uploads
│     (Trigger)         │  responseMode: "responseNode" (holds connection open)
└──────┬───────────────┘
       ▼
┌──────────────────────┐
│  2. Code: Save        │  helpers.getBinaryDataBuffer(i, key) → write to /data/inbox/
│     uploads to inbox  │
└──────┬───────────────┘
       ▼
┌──────────────────────┐
│  3. Execute: Stage 1  │  python3 01_normalize.py
│     normalize         │  .log → .txt, classify AGG vs switch, reject binary
└──────┬───────────────┘
       ▼
┌──────────────────────┐
│  4. Execute: Stage 2  │  python3 02_parse.py
│     parse configs     │  Extract ports, VLANs, QoS, SNMP → parsed.json
└──────┬───────────────┘
       ▼
┌──────────────────────┐
│  5. Execute: Stage 3  │  python3 03_generate_xlsx.py
│     generate xlsx     │  Build styled Canevas workbook
└──────┬───────────────┘
       ▼
┌──────────────────────┐
│  6. Code: Attach xlsx │  helpers.setBinaryDataBuffer() → attach file as binary
└──────┬───────────────┘
       ▼
┌──────────────────────┐
│  7. Respond to        │  Send xlsx back as HTTP response
│     Webhook           │
└──────────────────────┘
```

### Data Flow on Disk (via Volume Mount)

```
Host (Windows)                    Container (Alpine Linux)
─────────────                     ────────────────────────
n8n_data/                    →    /data/
  inbox/                          /data/inbox/        (uploaded files)
  staging/                        /data/staging/
    configs/                        /data/staging/configs/   (normalized)
    switches/                       /data/staging/switches/  (switch configs)
  out/                            /data/out/          (generated xlsx)
  parsed.json                     /data/parsed.json   (intermediate JSON)
```

---

## 7. The Dockerfile — Extending n8n with Python

```dockerfile
# Line 1-2: Documentation comment
# Build context = the project root ("08 verify"), i.e.:
#   docker build -f n8n_chain/n8n/Dockerfile ../..

# Line 5: Base image
FROM docker.n8n.io/n8nio/n8n:2.0.2
```
**Why this base image?** It's the official n8n image, pinned to version 2.0.2 for reproducibility. It runs Alpine Linux (small footprint) with Node.js pre-installed.

```dockerfile
# Line 7: Switch to root for installations
USER root
```
**Why?** The n8n image runs as the `node` user (non-root) for security. But installing packages requires root. We switch back later.

```dockerfile
# Lines 8-10: Install Python + openpyxl
RUN apk add --no-cache python3 py3-pip && \
    (python3 -m pip install --no-cache-dir --break-system-packages openpyxl \
     || python3 -m pip install --no-cache-dir openpyxl)
```
**Why `apk`?** Alpine uses `apk` (not `apt` or `pip`). The `--no-cache` flag keeps the image small. The fallback (`||`) handles different pip versions across n8n releases.

```dockerfile
# Lines 12-17: Copy our Python scripts into the image
COPY parse_configs.py fill_infovista.py /opt/scripts/
COPY n8n_chain/01_normalize.py \
     n8n_chain/02_parse.py \
     n8n_chain/03_generate_xlsx.py \
     /opt/scripts/n8n_chain/
```
**Why bake scripts into the image?** These are *application code*, not data. They should be versioned with the Dockerfile and deployed as a unit. The `COPY` paths are relative to the build context (`../..` = project root).

```dockerfile
# Line 19: Create data directories
RUN mkdir -p /data/inbox /data/staging /data/out && chown -R node:node /data
```
**Why?** Python scripts write to `/data/out/`. The `node` user needs write permission.

> **⚠️ GOTCHA:** This `mkdir` is useless at runtime if you mount a volume over `/data` — the volume overlay hides it. See [Section 12](#12-volume-mounts--the-silent-directory-killer).

```dockerfile
# Line 20: Switch back to non-root user
USER node
```
**Why?** Security best practice. n8n should never run as root.

---

## 8. The docker-compose.yml — Wiring It All Together

```yaml
services:
  n8n:
    build:
      context: ../..                              # ← Project root
      dockerfile: n8n_chain/n8n/Dockerfile        # ← Path to Dockerfile
```
**Why `context: ../..`?** The Dockerfile `COPY` commands reference files relative to the build context. Since `parse_configs.py` is at the project root, the context must be the project root, not the `n8n/` folder.

```yaml
    container_name: n8n-rax
    restart: unless-stopped
```
**`restart: unless-stopped`** — If the container crashes or the server reboots, Docker restarts it automatically.

```yaml
    ports:
      - "5678:5678"
```
**Port mapping** — `host_port:container_port`. n8n listens on 5678 inside the container. This maps it to 5678 on your machine. Access: `http://localhost:5678`

```yaml
    environment:
      NODE_FUNCTION_ALLOW_BUILTIN: fs,path
```
**Why?** Code nodes run in a sandboxed VM. By default, `require('fs')` is blocked. This env var whitelists the `fs` and `path` built-in modules. Without this, the "Save uploads" node crashes with `Cannot find module 'fs'`.

```yaml
      N8N_DEFAULT_BINARY_DATA_MODE: memory
```
**What this does:** Controls how n8n stores binary data internally. `memory` = base64 in memory. `filesystem` = UUID-referenced files on disk. **Note:** This does NOT affect how Code nodes access binary data — you must use `helpers.getBinaryDataBuffer()` regardless. See [Section 10](#10-binary-data-in-n8n--the-big-gotcha).

```yaml
      N8N_SECURE_COOKIE: "false"
```
**Why?** Allows the n8n web UI to work over plain HTTP (not just HTTPS). Needed for local development.

```yaml
      GENERIC_TIMEZONE: Africa/Casablanca
```
Sets the timezone for `$now` and `$today` variables in the workflow.

```yaml
    volumes:
      - n8n_home:/home/node/.n8n          # Persistent n8n data (workflows, credentials)
      - ../../n8n_data:/data              # Shared pipeline workspace
```
**Two types of volumes:**
- **Named volume** (`n8n_home:`) — Managed by Docker, survives container rebuilds, stores n8n's internal data
- **Bind mount** (`../../n8n_data:/data`) — Maps a host directory directly, visible from both host and container

```yaml
volumes:
  n8n_home:              # Declares the named volume
```

---

## 9. The Workflow — Node by Node

### Node 1: Webhook (Trigger)

```json
{
  "type": "n8n-nodes-base.webhook",
  "parameters": {
    "httpMethod": "POST",
    "path": "rax-integration",
    "responseMode": "responseNode",
    "options": {}
  }
}
```

**What it does:** Creates an HTTP endpoint at `http://localhost:5678/webhook/rax-integration`. When you POST files to this URL, the workflow triggers.

**`responseMode: "responseNode"`** — This is critical. It tells the Webhook: "Don't respond immediately. Wait until a Respond to Webhook node sends the response." Without this, n8n responds with `200 OK` immediately and the Respond node becomes "unused" → error.

**Data produced:** Each uploaded file becomes one item with `item.binary[key]` containing metadata (fileName, mimeType) and a data reference.

### Node 2: Code — Save Uploads to Inbox

```javascript
const fs = require('fs');
const path = require('path');
const inbox = '/data/inbox';
fs.rmSync(inbox, {recursive: true, force: true});
fs.mkdirSync(inbox, {recursive: true});

const items = $input.all();
let saved = 0;
for (let i = 0; i < items.length; i++) {
  const item = items[i];
  if (item.binary) {
    for (const [key, b] of Object.entries(item.binary)) {
      const name = b.fileName || ('upload_' + saved);
      const buf = await helpers.getBinaryDataBuffer(i, key);
      fs.writeFileSync(path.join(inbox, name), buf);
      saved++;
    }
  }
}
return [{json: {saved_to_inbox: saved}}];
```

**Key concepts:**
- `$input.all()` — Returns all input items as an array
- `helpers.getBinaryDataBuffer(i, key)` — The ONLY correct way to read binary data. Returns a `Buffer` with the actual file content
- `b.fileName` — Original filename from the upload
- The node collapses all items into a single output item (`[{json: {saved_to_inbox: saved}}]`)

### Node 3-5: Execute Command — Python Pipeline

```json
{"command": "python3 /opt/scripts/n8n_chain/01_normalize.py --inbox /data/inbox --out /data/staging"}
```

**What it does:** Runs a shell command inside the container. The Python scripts read/write files on the shared `/data` volume.

**Why three separate nodes?** Observability. Each stage shows its own output, exit code, and timing in the n8n UI. If parsing fails, you see exactly which stage failed.

**Data flow:** These nodes pass through the input items unchanged. The real data flows through files on disk, not through the n8n item pipeline.

### Node 6: Code — Attach xlsx

```javascript
const fs = require('fs');
const p = '/data/out/Canevas_Integration.xlsx';
const buf = fs.readFileSync(p);
const binaryData = await helpers.setBinaryDataBuffer(
  {
    mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    fileName: 'Canevas_Integration_RAX_AGG.xlsx',
  },
  buf
);
return [{
  json: {file: 'Canevas_Integration_RAX_AGG.xlsx'},
  binary: { data: binaryData },
}];
```

**Key concept:** `helpers.setBinaryDataBuffer()` takes a Buffer and returns a proper n8n binary data object. This is the counterpart to `getBinaryDataBuffer()`. Never construct binary items manually with `data.toString('base64')` — it bypasses n8n's binary data management.

### Node 7: Respond to Webhook

```json
{
  "type": "n8n-nodes-base.respondToWebhook",
  "parameters": {
    "respondWith": "allIncomingItems"
  }
}
```

**What it does:** Sends the binary data from the input items back as the HTTP response body. The curl command receives the xlsx file.

**`respondWith: "allIncomingItems"`** — Sends all items. Since we have one item with a binary attachment, it sends that file.

---

## 10. Binary Data in n8n — The Big Gotcha

This is the #1 trap for n8n beginners. Here's what happens:

### What You'd Expect

```javascript
// Seems logical...
const buf = Buffer.from(item.binary.data.data, 'base64');
```

### What Actually Happens

In n8n v2.0.2, `item.binary[key].data` is **NOT** the file content. It's an **internal reference** — either:
- A UUID string pointing to a file on disk (filesystem mode, the default)
- A base64 string (memory mode)

**Either way, you should never access `.data` directly.**

### The Correct Way

```javascript
// ALWAYS use the helpers API:
const buf = await helpers.getBinaryDataBuffer(itemIndex, binaryPropertyKey);
```

This function abstracts away the storage mode. It returns a proper `Buffer` regardless of whether n8n stores data on disk or in memory.

### Why We Hit This Bug

Our original Code node did:
```javascript
fs.writeFileSync(path.join(inbox, name), Buffer.from(b.data, 'base64'));
```

With filesystem mode (default), `b.data` was a UUID like `"9c9d31ab-1a6c-4e1d-981b-6e80604cd419"`. `Buffer.from(uuid, 'base64')` decoded the UUID string itself into 9 bytes of garbage. Every uploaded file became a 9-byte junk file.

**The debugging journey:**
1. Parser reported "0 ports, 0 VLANs, 0 interfaces" — configs were empty
2. Added debug logging → files were 9 bytes: `~)^+-zo`
3. Checked n8n's binary data directory → real files were 12KB+ on disk
4. The 9 bytes were the base64 decoding of the UUID reference string!

### The Fix

```javascript
// Read binary data properly:
const buf = await helpers.getBinaryDataBuffer(i, key);
fs.writeFileSync(path.join(inbox, name), buf);

// Write binary data properly:
const binaryData = await helpers.setBinaryDataBuffer(
  { mimeType: 'application/...', fileName: 'output.xlsx' },
  buffer
);
```

### The Golden Rule

> **Never touch `item.binary[key].data` directly. Always use `helpers.getBinaryDataBuffer()` and `helpers.setBinaryDataBuffer()`.**

---

## 11. The Code Node Sandbox — What You Can and Cannot Do

n8n runs Code node JavaScript in a **sandboxed VM** (vm2). This is for security — it prevents rogue code from crashing the n8n process.

### What's Available

| Variable | Description |
|----------|-------------|
| `$input` | Access to input items (`.all()`, `.first()`, `.item`) |
| `$json` | Shorthand for current item's JSON data |
| `$now`, `$today` | Current date/time |
| `$env` | Access to environment variables |
| `$node` | Access to other nodes' output |
| `helpers` | Binary data, HTTP requests, etc. |
| `require()` | Only whitelisted modules (controlled by `NODE_FUNCTION_ALLOW_BUILTIN`) |

### What's NOT Available

- Direct access to n8n's internal database
- Network requests to arbitrary hosts (use `helpers.httpRequest` instead)
- `process`, `global` (sandboxed)
- Modules not in the whitelist (e.g., `child_process`, `os`)

### The `helpers` Object

This is your bridge to n8n's capabilities:

```javascript
helpers.getBinaryDataBuffer(itemIndex, key)  // Read binary → Buffer
helpers.setBinaryDataBuffer(meta, buffer)     // Write Buffer → binary
helpers.httpRequest(options)                  // Make HTTP requests
```

The `helpers` object comes from the execution context (`this.helpers` in n8n internals), exposed as a global in the sandbox via `getSandboxContext()`.

---

## 12. Volume Mounts — The Silent Directory Killer

### The Bug

Our Dockerfile creates `/data/out/`:
```dockerfile
RUN mkdir -p /data/inbox /data/staging /data/out
```

But at runtime, `/data/out/` doesn't exist. Python crashes with:
```
FileNotFoundError: [Errno 2] No such file or directory: '/data/out/Canevas_Integration.xlsx'
```

### Why?

The docker-compose.yml mounts a bind volume over `/data`:
```yaml
volumes:
  - ../../n8n_data:/data
```

**A bind mount completely replaces the target directory.** The container sees the host's `n8n_data/` folder, not the image's `/data/`. Since the host's `n8n_data/` only had `inbox/` and `staging/` (no `out/`), the directory "disappeared."

```
Image's /data/          Host's n8n_data/        Container sees:
  inbox/                  inbox/                   inbox/
  staging/                staging/                 staging/
  out/                    (doesn't exist)          (nothing!)
```

### The Fix (Two Parts)

1. **Create the directory on the host:**
   ```powershell
   mkdir n8n_data\out
   ```

2. **Make the script resilient** — create the directory if missing:
   ```python
   os.makedirs(os.path.dirname(args.out), exist_ok=True)
   ```

### The Lesson

> **Never rely on `RUN mkdir` in a Dockerfile for paths that will be overlaid by a volume mount.** Either create the directory on the host, or have your application create it at runtime with `os.makedirs(..., exist_ok=True)`.

---

## 13. The Webhook + Respond Pattern — Closing the HTTP Loop

### How It Works

```
curl -F "file=@config.txt" http://localhost:5678/webhook/rax-integration
         │
         ▼
┌────────────────────────────────────────────────────────────┐
│  n8n Webhook                                                │
│  1. Receives the HTTP request                               │
│  2. responseMode="responseNode" → holds the connection open │
│  3. Triggers the workflow                                   │
│  4. Workflow runs...                                        │
│  5. Respond to Webhook node sends the response              │
│  6. HTTP connection closes, curl receives the file          │
└────────────────────────────────────────────────────────────┘
```

### The Two Response Modes

| Mode | Behavior | When to use |
|------|----------|-------------|
| `"onReceived"` (default) | Responds immediately with `200 OK`, no body | Fire-and-forget webhooks |
| `"responseNode"` | Holds connection until a Respond to Webhook node runs | When you need to return data |

### The Error You'll Hit

If you have a Respond to Webhook node but forget `responseMode: "responseNode"`:

```
WorkflowConfigurationError: Unused Respond to Webhook node found in the workflow
```

n8n detects that the Webhook is in "onReceived" mode (responds immediately) and the Respond node will never be reached. It throws an error instead of silently ignoring the node.

### The Matching Pair

These two nodes MUST be configured together:

```
Webhook node:        responseMode: "responseNode"
Respond to Webhook:  respondWith: "allIncomingItems"
```

Miss either one and the pipeline breaks.

---

## 14. All the Bugs We Hit (So You Don't Have To)

### Bug 1: "Unused Respond to Webhook node"

**Symptom:** `WorkflowConfigurationError: Unused Respond to Webhook node found`
**Cause:** Webhook node missing `responseMode: "responseNode"`
**Fix:** Add `"responseMode": "responseNode"` to the Webhook parameters

### Bug 2: "FileNotFoundError: /data/out/"

**Symptom:** Python crashes trying to write to `/data/out/`
**Cause:** Volume mount `n8n_data:/data` hides the Dockerfile's `mkdir /data/out`
**Fix:** Create `n8n_data/out/` on the host + add `os.makedirs()` in Python

### Bug 3: "PermissionError: /data/out/Canevas_Integration.xlsx"

**Symptom:** Python crashes trying to overwrite the xlsx
**Cause:** Excel lock file (`~$Canevas_Integration.xlsx`) from having the file open
**Fix:** Close the Excel file before re-running the workflow

### Bug 4: "0 ports, 0 VLANs, 0 interfaces" (the silent killer)

**Symptom:** Parser finds files but extracts nothing. Debug shows 9-byte garbage files.
**Cause:** `Buffer.from(b.data, 'base64')` decodes the UUID reference, not the file content
**Fix:** Use `await helpers.getBinaryDataBuffer(i, key)` instead of `Buffer.from(b.data, 'base64')`

### Bug 5: "Cannot find module 'fs'"

**Symptom:** Code node crashes on `require('fs')`
**Cause:** n8n sandboxes Code nodes; `fs` is blocked by default
**Fix:** Set `NODE_FUNCTION_ALLOW_BUILTIN: fs,path` in environment

### Bug 6: Empty xlsx returned by curl

**Symptom:** curl receives a tiny/empty file
**Cause:** "Attach xlsx" node constructs binary manually with `data.toString('base64')`, bypassing n8n's binary data management
**Fix:** Use `await helpers.setBinaryDataBuffer({mimeType, fileName}, buffer)`

---

## 15. Quick Reference Cheat Sheet

### Docker Commands

```bash
# Build and start
cd n8n_chain/n8n
docker compose up --build -d

# View logs
docker compose logs -f

# Rebuild after code changes
docker compose up --build -d

# Execute command inside container
docker exec n8n-rax sh -c "ls -la /data/inbox/"

# Stop
docker compose down
```

### n8n Web UI

```
http://localhost:5678
```

Import workflow: Menu → Import from File → select `workflow.json`
Activate: Toggle the "Active" switch in the workflow editor

### Testing with curl

```powershell
curl.exe -o "$env:USERPROFILE\Desktop\output.xlsx" `
  -F "f1=@config1.txt" `
  -F "f2=@config2.txt" `
  -F "f3=@switch_dump.log" `
  http://localhost:5678/webhook/rax-integration
```

### n8n Binary Data API

```javascript
// READ binary data (in Code node):
const buf = await helpers.getBinaryDataBuffer(itemIndex, propertyKey);

// WRITE binary data (in Code node):
const binaryData = await helpers.setBinaryDataBuffer(
  { mimeType: 'application/octet-stream', fileName: 'output.bin' },
  buffer
);

// Return item with binary attachment:
return [{ json: { name: 'file.bin' }, binary: { data: binaryData } }];
```

### Key Environment Variables

| Variable | Purpose | Our Value |
|----------|---------|-----------|
| `NODE_FUNCTION_ALLOW_BUILTIN` | Whitelist Node.js built-ins for Code nodes | `fs,path` |
| `N8N_DEFAULT_BINARY_DATA_MODE` | Binary storage backend (`memory` or `filesystem`) | `memory` |
| `N8N_SECURE_COOKIE` | Allow HTTP (not just HTTPS) for web UI | `false` |
| `GENERIC_TIMEZONE` | Timezone for `$now` / `$today` | `Africa/Casablanca` |

---

## Summary: The Mental Model

```
┌─────────────────────────────────────────────────────────┐
│  Docker                                                  │
│  ┌─────────────────────────────────────────────────────┐ │
│  │  Container (Alpine Linux)                            │ │
│  │                                                      │ │
│  │  n8n (Node.js)          Python 3 + openpyxl          │ │
│  │  ┌──────────┐           ┌──────────────────────┐    │ │
│  │  │ Webhook   │──→JS────→│ Execute Command      │    │ │
│  │  │ (HTTP in) │           │ (python3 script.py)  │    │ │
│  │  └──────────┘           └──────────────────────┘    │ │
│  │       │                          │                   │ │
│  │       ▼                          ▼                   │ │
│  │  /data/inbox/  ──→  /data/staging/  ──→  /data/out/ │ │
│  │       ▲                          │         │         │ │
│  └───────┼──────────────────────────┼─────────┼─────────┘ │
│          │      Volume Mount        │         │           │
│  ┌───────┼──────────────────────────┼─────────┼─────┐    │
│  │  n8n_data/    ◄───── Shared ────►│         │     │    │
│  │  inbox/    staging/    out/      ◄─────────┘     │    │
│  └──────────────────────────────────────────────────┘    │
│                                                          │
│  Host (Windows)                                          │
└─────────────────────────────────────────────────────────┘
```

**The Dockerfile** builds the image (n8n + Python + scripts).
**The docker-compose.yml** configures the runtime (ports, volumes, env).
**The workflow** orchestrates the flow (webhook → save → parse → generate → respond).
**The helpers API** is your bridge between n8n's world and the filesystem.

Remember the golden rules:
1. **Binary data:** Always use `helpers.getBinaryDataBuffer()` / `setBinaryDataBuffer()`
2. **Volume mounts:** Create directories on the host, not just in the Dockerfile
3. **Webhook response:** Match `responseMode: "responseNode"` with a Respond to Webhook node
4. **Code node modules:** Whitelist with `NODE_FUNCTION_ALLOW_BUILTIN`
5. **Excel files:** Close them before re-running the pipeline
