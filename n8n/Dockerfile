# ──────────────────────────────────────────────────────────────
# n8n Parser Pipeline — Docker Image
# ──────────────────────────────────────────────────────────────
# Extends the official n8n image with Python 3 + openpyxl so the
# pipeline scripts can run your parser and generate Excel output.
#
# Build context = repo root:
#   docker compose up --build -d
#
# Or manually:
#   docker build -f n8n/Dockerfile -t n8n-parser-pipeline .
# ──────────────────────────────────────────────────────────────

FROM docker.n8n.io/n8nio/n8n:2.0.2

USER root

# Install Python 3 + openpyxl (for Excel generation)
RUN apk add --no-cache python3 py3-pip && \
    (python3 -m pip install --no-cache-dir --break-system-packages openpyxl \
     || python3 -m pip install --no-cache-dir openpyxl)

# Pipeline orchestration scripts
COPY scripts/01_normalize.py \
     scripts/02_parse.py \
     scripts/03_generate.py \
     /opt/scripts/pipeline/

# Your parser module (bring your own parser)
COPY scripts/your_parser.py /opt/scripts/parse_module.py

# Create data directories and set permissions
RUN mkdir -p /data/inbox /data/staging/configs /data/staging/switches /data/out \
    && chown -R node:node /data

USER node
