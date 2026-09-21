#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"


def main() -> None:
    index = (WEB / "index.html").read_text(encoding="utf-8")
    teacher = (WEB / "teacher.html").read_text(encoding="utf-8")
    app_js = (WEB / "app.js").read_text(encoding="utf-8")
    teacher_js = (WEB / "teacher.js").read_text(encoding="utf-8")
    style = (WEB / "style.css").read_text(encoding="utf-8")
    errors = []
    if "cdnjs.cloudflare.com" in index or "cdnjs.cloudflare.com" in teacher:
        errors.append("CDN leftover in HTML")
    vendor = WEB / "vendor" / "codemirror" / "lib" / "codemirror.min.js"
    license_file = WEB / "vendor" / "codemirror" / "LICENSE"
    if not vendor.is_file():
        errors.append("missing vendored CodeMirror")
    if not license_file.is_file():
        errors.append("missing CodeMirror LICENSE")
    if 'aria-live="polite"' not in index or 'role="progressbar"' not in index:
        errors.append("student page missing live region or progressbar")
    if 'aria-live="polite"' not in teacher:
        errors.append("teacher page missing live region")
    if "X-CSRF-Token" not in app_js or "X-CSRF-Token" not in teacher_js:
        errors.append("frontend missing CSRF header")
    if "localStorage.getItem(\"solved\")" in app_js:
        errors.append("client still treats localStorage.solved as source of truth")
    if "prefers-reduced-motion" not in style:
        errors.append("missing reduced motion")
    if errors:
        raise SystemExit("\n".join(errors))
    print("frontend smoke ok")


if __name__ == "__main__":
    main()
