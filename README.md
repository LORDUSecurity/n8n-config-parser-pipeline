# n8n Parser Pipeline

**Upload files via HTTP → parse → generate Excel → download.**

A Docker-based pipeline template that turns any Python parser into an HTTP-accessible automation service. Bring your own parser, plug it in, and get a webhook-driven workflow with styled Excel output — in minutes, not hours.

---

## What This Does

```
curl -F "file=@data.txt" http://localhost:5678/webhook/pipeline
```

That single command triggers a 5-stage pipeline that:

1. Receives your files over HTTP
2. Normalizes and classifies them
3. Parses them with **your** Python parser
4. Generates a styled Excel workbook
5. Returns the file as the HTTP response

The pipeline handles all the infrastructure. You provide the domain logic.

---

## Architecture

```
                        ┌─────────────────────────────────────────┐
                        │           Docker Container               │
                        │                                         │
  HTTP POST ───────────►│  ┌──────────┐                           │
  (multipart files)     │  │ Webhook   │  n8n workflow engine      │
                        │  └────┬─────┘                           │
                        │       ▼                                  │
                        │  ┌──────────┐   /data/inbox/             │
                        │  │ Code:    │──► save files to disk      │
                        │  │ Save     │                            │
                        │  └────┬─────┘                            │
                        │       ▼                                  │
                        │  ┌──────────┐                            │
                        │  │ Stage 1  │  01_normalize.py           │
                        │  │ Normalize│  classify, rename, reject  │
                        │  └────┬─────┘                            │
                        │       ▼                                  │
                        │  ┌──────────┐                            │
                        │  │ Stage 2  │  02_parse.py               │
                        │  │ Parse    │  YOUR parser module (pc)   │
                        │  └────┬─────┘                            │
                        │       ▼                                  │
                        │  ┌──────────┐                            │
                        │  │ Stage 3  │  03_generate.py            │
                        │  │ Generate │  YOUR table maker (pc)     │
                        │  └────┬─────┘                            │
                        │       ▼                                  │
                        │  ┌──────────┐                            │
                        │  │ Code:    │  attach xlsx as binary     │
                        │  │ Attach   │                            │
                        │  └────┬─────┘                            │
                        │       ▼                                  │
                        │  ┌──────────┐                            │
  ◄─────────────────────│  │ Respond  │  xlsx in HTTP response     │
  (Excel file)          │  └──────────┘                            │
                        │                                         │
                        │  /data/inbox → /data/staging → /data/out │
                        └────────┬────────────────────────────────┘
                                 │
                          Volume Mount
                                 │
                        ┌────────▼────────┐
                        │   data/ (host)   │
                        │  inbox/ staging/ │
                        │  out/            │
                        └─────────────────┘
```

### Why This Design?

| Concern | How it's solved |
|---------|----------------|
| **HTTP endpoint** | n8n Webhook node — no Flask/FastAPI boilerplate |
| **File upload handling** | n8n manages multipart decoding and binary data |
| **Pipeline orchestration** | Visual node chain with per-stage error tracking |
| **Parser isolation** | Your parser is a Python module, not tangled with n8n |
| **Reproducibility** | Docker image pins all dependencies |
| **Extensibility** | Swap the parser module, keep everything else |

---

## Quick Start

```bash
# 1. Clone and enter the repo
git clone <your-repo-url>
cd n8n-parser-pipeline

# 2. Start the pipeline
docker compose up --build -d

# 3. Import the workflow
#    Open http://localhost:5678 → Import from File → select n8n/workflow.json

# 4. Activate the workflow in the n8n UI

# 5. Test it
curl -o output.xlsx \
     -F "file=@data/inbox/sample.txt" \
     http://localhost:5678/webhook/pipeline
```

---

## Bring Your Own Parser (BYOP)

The pipeline is parser-agnostic. Stages 2 and 3 import a Python module (`pc`) that must expose two functions. Here's the contract:

### The Interface

Create a file called `your_parser.py` and implement these two functions:

```python
def process_all_files(directory: str) -> dict:
    """
    Parse all files in a directory.
    
    Args:
        directory: Path containing normalized config/data files.
    
    Returns:
        Dict of {device_name: parsed_data_dict}.
        Each parsed_data_dict should contain whatever your
        Excel generator needs (ports, records, metadata, etc.)
    """
    ...


def generate_excel(
    data: dict,
    output_path: str,
    switch_dir: str = None,
    switch_devices: dict = None,
) -> None:
    """
    Generate a styled Excel workbook from parsed data.
    
    Args:
        data:            The dict returned by process_all_files().
        output_path:     Where to write the .xlsx file.
        switch_dir:      Optional path to secondary device configs.
        switch_devices:  Optional dict of secondary parsed devices.
    """
    ...
```

### Wiring It Up

1. Place your parser module in `scripts/your_parser.py`
2. Update the Dockerfile to copy it:

```dockerfile
COPY scripts/your_parser.py /opt/scripts/parse_module.py
```

3. Rebuild:

```bash
docker compose up --build -d
```

That's it. The pipeline scripts (`02_parse.py`, `03_generate.py`) import your module as `pc` and call `pc.process_all_files()` and `pc.generate_excel()`.

### Example: CSV Parser

The `templates/` folder includes a working CSV parser example:

| File | Purpose |
|------|---------|
| `templates/parser_template.py` | Documented interface contract |
| `templates/example_csv_parser.py` | Working CSV → Excel parser |
| `templates/sample_data.csv` | Sample input file |

Try the example:

```bash
# Copy the example parser into place
cp templates/example_csv_parser.py scripts/your_parser.py

# Rebuild and restart
docker compose up --build -d

# Upload a CSV file
curl -o report.xlsx \
     -F "file=@templates/sample_data.csv" \
     http://localhost:5678/webhook/pipeline
```

---

## The Three Stages

### Stage 1: Normalize (`01_normalize.py`)

Prepares raw uploads for parsing:

- Classifies files by naming convention (e.g., IP-named files → "switch" category)
- Converts `.log` → `.txt` for uniform handling
- Rejects binary files (xlsx, zip, pdf) with clear error messages
- Validates that files contain text content (not corrupted)
- Organizes into `staging/configs/` and `staging/switches/`

**You typically don't need to modify this stage.**

### Stage 2: Parse (`02_parse.py`)

Runs your parser on the normalized files:

- Calls `pc.process_all_files(staging/configs/)` for primary devices
- Calls `pc.process_all_files(staging/switches/)` for secondary devices
- Writes a single `parsed.json` combining all results
- Outputs device counts and record counts for observability

**This is where your parser lives.**

### Stage 3: Generate (`03_generate.py`)

Builds the output workbook:

- Reads `parsed.json`
- Calls `pc.generate_excel(data, output_path, ...)` to produce styled output
- Creates the output directory if it doesn't exist

**Your `generate_excel()` function controls the output format.**

---

## Project Structure

```
n8n-parser-pipeline/
├── README.md                  ← You are here
├── .gitignore
├── docker-compose.yml         ← Runtime config (ports, volumes, env)
├── n8n/
│   ├── Dockerfile             ← Image: n8n + Python + your parser
│   └── workflow.json          ← The n8n workflow (import this)
├── scripts/
│   ├── 01_normalize.py        ← Stage 1: file classification
│   ├── 02_parse.py            ← Stage 2: calls your parser
│   ├── 03_generate.py         ← Stage 3: calls your table maker
│   └── your_parser.py         ← ★ YOUR PARSER GOES HERE ★
├── templates/
│   ├── parser_template.py     ← Interface contract (documented)
│   ├── example_csv_parser.py  ← Working example (CSV → Excel)
│   └── sample_data.csv        ← Sample input
├── data/                      ← Shared workspace (volume mount)
│   ├── inbox/                 ← Raw uploads
│   ├── staging/               ← Normalized files
│   │   ├── configs/
│   │   └── switches/
│   └── out/                   ← Generated Excel output
└── docs/
    └── n8n-course.md          ← Deep-dive course: how it all works
```

---

## Key Design Decisions

### Why Docker Compose + Dockerfile (Not Just One)?

The **Dockerfile** defines *what's inside the image* (n8n + Python + your parser).  
The **docker-compose.yml** defines *how the container runs* (ports, volumes, env vars).

This separation means you can:
- Rebuild the image without changing runtime config
- Change ports/volumes without rebuilding
- Deploy the same image to different environments

### Why n8n Instead of Flask/FastAPI?

| You'd need to build | n8n provides for free |
|---------------------|----------------------|
| HTTP server + routing | Webhook node |
| Multipart file parsing | Built-in binary data management |
| Pipeline error handling | Visual per-node execution tracking |
| Execution history/logs | Built-in execution inspector |
| Manual workflow triggering | One-click or webhook trigger |
| Response construction | Respond to Webhook node |

### Why Volume Mounts?

The `data/` folder is shared between your host and the container. This means:
- You can drop files into `data/inbox/` directly (no HTTP needed)
- You can inspect intermediate results in `data/staging/`
- You can grab the output xlsx from `data/out/` without going through HTTP
- Your data persists across container restarts

---

## Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `NODE_FUNCTION_ALLOW_BUILTIN` | Node.js modules available to Code nodes | `fs,path` |
| `N8N_DEFAULT_BINARY_DATA_MODE` | Binary storage backend | `memory` |
| `N8N_SECURE_COOKIE` | Allow HTTP (not just HTTPS) | `false` |
| `GENERIC_TIMEZONE` | Timezone for `$now`/`$today` | `UTC` |

---

## Gotchas & Lessons Learned

This project was built through real debugging sessions. Here's what we learned:

**1. Binary data in n8n Code nodes** — Never access `item.binary[key].data` directly. It's an internal reference (UUID), not file content. Always use `helpers.getBinaryDataBuffer(i, key)`.

**2. Volume mounts hide Dockerfile directories** — If your Dockerfile does `RUN mkdir /data/out` but you mount a volume over `/data`, the mkdir is invisible. Create directories on the host side too.

**3. Webhook response mode** — If you use a "Respond to Webhook" node, the Webhook trigger must have `responseMode: "responseNode"`. Otherwise n8n responds immediately and flags the Respond node as unused.

**4. Excel lock files** — If the output xlsx is open in Excel, the container can't overwrite it. Close the file before re-running.

**5. Code node sandbox** — `require('fs')` is blocked by default. Set `NODE_FUNCTION_ALLOW_BUILTIN: fs,path` to whitelist modules.

Read the full deep-dive in [`docs/n8n-course.md`](docs/n8n-course.md).

---

## License

MIT
