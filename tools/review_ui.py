#!/usr/bin/env python3
"""Append the optional client-only feedback layer without replacing the report engine."""
from __future__ import annotations
import hashlib
from pathlib import Path
HOME=Path(__file__).resolve().parent.parent
ASSETS=HOME/'tools/review_assets'
VERSION='1.0.0'
START='<!-- HEXIPLAN_TARGETED_REVIEW_BEGIN -->'
END='<!-- HEXIPLAN_TARGETED_REVIEW_END -->'

def asset_manifest():
    return {p.relative_to(HOME).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (ASSETS/'review.css',ASSETS/'review.js')}

def attach_review(text: str) -> str:
    if START in text:
        raise ValueError('Feedback layer is already attached; regenerate from source, not submitted HTML.')
    css=(ASSETS/'review.css').read_text(encoding='utf-8')
    script=(ASSETS/'review.js').read_text(encoding='utf-8')
    if '</script' in script.lower():raise ValueError('Unexpected HTML closing tag in feedback script.')
    payload=START+'\n<style>'+css+'</style>\n<script>'+script+'</script>\n'+END
    if '</body>' not in text:raise ValueError('Report shell has no closing body.')
    left,right=text.rsplit('</body>',1)
    return left+payload+'\n</body>'+right
