"""Reject personal build paths and debug symbols in public release artifacts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import zipfile

PROFILE_PATH = re.compile(
    r'(?i)(?:[A-Z]:[\\/]+Users[\\/]+[^\\/\s"<>\x00]+|'
    r'/(?:home|Users)/[^/\s"<>\x00]+/)'
)
PRIVATE_KEY = re.compile(r'-----BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY-----')


def artifact_errors(name: str, data: bytes) -> list[str]:
    errors = []
    if name.lower().endswith(('.pdb', '.pfx', '.p12', '.pem', '.key')):
        errors.append('private-key-or-symbol-file')
    # UTF-8 for PE CodeView/debug paths; both UTF-16 alignments for .NET strings.
    texts = [data.decode('utf-8', errors='ignore')]
    if b'\x00' in data:
        texts.extend(data[n:].decode('utf-16le', errors='ignore') for n in (0, 1))
    if any(PROFILE_PATH.search(text) for text in texts):
        errors.append('personal-profile-path')
    if any(PRIVATE_KEY.search(text) for text in texts):
        errors.append('private-key-header')
    return errors


def verify(path: Path) -> dict:
    errors = []
    if path.is_dir():
        entries = ((str(p.relative_to(path)), p.read_bytes())
                   for p in sorted(path.rglob('*')) if p.is_file())
        archive = None
    elif zipfile.is_zipfile(path):
        archive = zipfile.ZipFile(path)
        entries = ((i.filename, archive.read(i)) for i in archive.infolist() if not i.is_dir())
    else:
        archive = None
        entries = [(path.name, path.read_bytes())]
    count = 0
    try:
        for name, data in entries:
            count += 1
            errors.extend({'file': name, 'rule': rule} for rule in artifact_errors(name, data))
    finally:
        if archive:
            archive.close()
    return {'artifact': path.name, 'checked_files': count, 'errors': errors, 'passed': not errors}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('artifact', type=Path)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    result = verify(args.artifact)
    if args.report:
        args.report.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['passed'] else 1)


if __name__ == '__main__':
    main()
