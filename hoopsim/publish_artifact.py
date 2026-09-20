"""Turn the built single file into an artifact-ready page.

An artifact supplies its own document skeleton, so the `<!doctype>`, `<html>`,
`<head>` and `<body>` wrappers have to come off -- but nothing inside them may
change, or the published page and the downloadable file drift apart.

    python publish_artifact.py dist/hoopsim.html -o /tmp/publish.html
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

#: The sticky header sits under the notch on a phone, and the artifact frame
#: has no page gutter of its own.
ARTIFACT_CSS = """
header { top: env(safe-area-inset-top, 0px); }
main, header { padding-inline: 16px; }
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation-duration: .01ms !important;
    transition-duration: .01ms !important; }
}
"""

_SKELETON = re.compile(r"</?(?:!doctype|html|head|body)\b[^>]*>", re.I)


def convert(html: str) -> str:
    title = re.search(r"<title>(.*?)</title>", html, re.S)
    style = re.search(r"<style>(.*?)</style>", html, re.S)
    body = re.search(r"<body[^>]*>(.*)</body>", html, re.S)
    if not (style and body):
        raise ValueError("expected a <style> block and a <body> in the build")

    out = (f"<title>{title.group(1) if title else 'Hoopsim'}</title>\n"
           f"<style>{style.group(1)}{ARTIFACT_CSS}</style>\n"
           f"{body.group(1)}")

    leftover = _SKELETON.findall(out)
    if leftover:
        raise ValueError(f"document skeleton survived conversion: {leftover}")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("source", type=Path)
    ap.add_argument("-o", "--out", type=Path, required=True)
    args = ap.parse_args(argv)

    out = convert(args.source.read_text(encoding="utf-8"))
    args.out.write_text(out, encoding="utf-8")
    print(f"wrote {args.out} ({len(out) / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
