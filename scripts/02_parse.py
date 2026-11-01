#!/usr/bin/env python3
"""
Stage 2: Parse normalized files with the user-provided parser module.

The parser module is imported as `pc` and must expose:
    pc.process_all_files(directory) -> dict

Usage:
    python 02_parse.py --staging /data/staging --out /data/parsed.json
"""
import argparse
import json
import os
import sys

# Import the user's parser module
sys.path.insert(0, os.environ.get('PARSER_DIR', '/opt/scripts'))
import parse_module as pc  # noqa: E402


def _json_default(o):
    """Handle sets and bytes that may appear in parsed structures."""
    if isinstance(o, set):
        return sorted(o, key=str)
    if isinstance(o, bytes):
        return o.decode('utf-8', 'replace')
    return str(o)


def main():
    ap = argparse.ArgumentParser(description='Parse normalized files')
    ap.add_argument('--staging', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    cfg_dir = os.path.join(args.staging, 'configs')
    sw_dir = os.path.join(args.staging, 'switches')

    agg = pc.process_all_files(cfg_dir) if os.path.isdir(cfg_dir) else {}
    switches = pc.process_all_files(sw_dir) if os.path.isdir(sw_dir) else {}

    with open(args.out, 'w', encoding='utf-8') as fh:
        json.dump({'agg': agg, 'switches': switches}, fh, ensure_ascii=False,
                  default=_json_default)

    print(json.dumps({
        'primary_devices': len(agg),
        'secondary_devices': len(switches),
        'primary_records': sum(len(d.get('records', d.get('config_ports', [])))
                               for d in agg.values()),
        'secondary_records': sum(len(d.get('records', d.get('config_ports', [])))
                                 for d in switches.values()),
        'out': args.out,
    }))
    return 0


if __name__ == '__main__':
    sys.exit(main())
