"""
Simple copyright/license detection from HTML/text.
Searches for common license markers and copyright symbols.
"""
import re
from pathlib import Path

COPYRIGHT_RE = re.compile(r"©|Copyright|All rights reserved|All Rights Reserved", re.IGNORECASE)
LICENSE_KEYWORDS = [
    'license', 'licensed under', 'mit license', 'apache license', 'creative commons', 'cc-by', 'cc0'
]

def check_copyright_in_text(text: str) -> dict:
    res = {'copyright': False, 'license': None}
    if not text:
        return res
    if COPYRIGHT_RE.search(text):
        res['copyright'] = True
    low = text.lower()
    for kw in LICENSE_KEYWORDS:
        if kw in low:
            res['license'] = kw
            break
    return res

def check_copyright_in_file(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {'copyright': False, 'license': None}
    try:
        txt = p.read_text(encoding='utf-8', errors='ignore')
        return check_copyright_in_text(txt)
    except Exception:
        return {'copyright': False, 'license': None}

if __name__ == '__main__':
    print(check_copyright_in_text('This is © 2026 Example. Licensed under MIT License.'))
