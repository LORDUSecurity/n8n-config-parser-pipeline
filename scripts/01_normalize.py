#!/usr/bin/env python3
"""
Stage 1: Normalize incoming files.

Classifies uploads into primary configs and secondary devices,
converts file extensions for uniform handling, and rejects
binary/non-text uploads.

Usage:
    python 01_normalize.py --inbox /data/inbox --out /data/staging
"""
import argparse
import json
import os
import re
import sys

IP_NAME_RE = re.compile(r'^\d{1,3}(?:\.\d{1,3}){3}$')
NUM_EXT_RE = re.compile(r'^\.\d+$')


def is_text_bytes(data):
    """True when the payload looks like printable text."""
    if not data or b'\x00' in data:
        return False
    try:
        text = data.decode('utf-8')
    except UnicodeDecodeError:
        try:
            text = data.decode('cp1252')
        except UnicodeDecodeError:
            return False
    sample = text[:200000]
    bad = sum(1 for ch in sample
              if ord(ch) < 32 and ch not in '\t\n\r\f')
    return bad / max(len(sample), 1) < 0.01


def classify(name):
    """Determine file category: ('switch', ip) | ('config', name) | (None, reason)."""
    stem, ext = os.path.splitext(name)
    ext_l = ext.lower()
    if IP_NAME_RE.match(name):
        return 'switch', name + '.txt'
    if IP_NAME_RE.match(stem):
        return 'switch', stem + '.txt'
    if ext_l == '.log':
        return 'config', stem + '.txt'
    if ext_l == '.txt' or ext == '' or NUM_EXT_RE.match(ext):
        return 'config', name
    return None, 'unsupported extension %r' % ext


def main():
    ap = argparse.ArgumentParser(description='Normalize uploaded files')
    ap.add_argument('--inbox', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    os.makedirs(os.path.join(args.out, 'configs'), exist_ok=True)
    os.makedirs(os.path.join(args.out, 'switches'), exist_ok=True)

    accepted, rejected = [], []
    if os.path.isdir(args.inbox):
        for name in sorted(os.listdir(args.inbox)):
            src = os.path.join(args.inbox, name)
            if not os.path.isfile(src):
                continue
            with open(src, 'rb') as fh:
                data = fh.read()
            if not is_text_bytes(data):
                rejected.append({'file': name, 'reason': 'binary content'})
                continue
            kind, new_name = classify(name)
            if kind is None:
                rejected.append({'file': name, 'reason': new_name})
                continue
            dst = os.path.join(args.out,
                               'switches' if kind == 'switch' else 'configs',
                               new_name)
            with open(dst, 'wb') as fh:
                fh.write(data)
            accepted.append({'file': name, 'as': new_name, 'category': kind})

    print(json.dumps({
        'accepted': len(accepted),
        'rejected': len(rejected),
        'details': {'accepted': accepted, 'rejected': rejected},
    }))
    return 0


if __name__ == '__main__':
    sys.exit(main())
