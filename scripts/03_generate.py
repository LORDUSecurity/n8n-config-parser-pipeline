#!/usr/bin/env python3
"""
Stage 3: Generate styled Excel output with the user-provided parser module.

The parser module is imported as `pc` and must expose:
    pc.generate_excel(data, output_path, switch_dir, switch_devices) -> None

Usage:
    python 03_generate.py --json /data/parsed.json --out /data/out/Report.xlsx \
        [--switch-dir /data/staging/switches]
"""
import argparse
import json
import os
import sys

# Import the user's parser module
sys.path.insert(0, os.environ.get('PARSER_DIR', '/opt/scripts'))
import parse_module as pc  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description='Generate Excel output')
    ap.add_argument('--json', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--switch-dir', default=None)
    args = ap.parse_args()

    with open(args.json, encoding='utf-8') as fh:
        data = json.load(fh)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)

    pc.generate_excel(
        data.get('agg', {}),
        args.out,
        switch_dir=args.switch_dir,
        switch_devices=data.get('switches') or None,
    )
    print(json.dumps({'out': args.out,
                      'primary_devices': len(data.get('agg', {})),
                      'secondary_devices': len(data.get('switches') or {})}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
