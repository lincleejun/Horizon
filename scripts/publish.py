#!/usr/bin/env python3
"""Publish a Horizon summary: full page via share-page, compact digest to WeChat via Hermes.

Usage: python scripts/publish.py [data/summaries/horizon-YYYY-MM-DD-zh.md] [--no-send]
Defaults to the newest summary.
"""

import html
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

SHARE = Path.home() / ".claude/skills/share-page/share"
WECHAT_LIMIT = 4000  # iLink caps one message at ~4000 chars

PAGE = """<!doctype html><html lang="zh"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>%s</title>
<style>:root{--bg:#fafaf7;--fg:#1c1c1a;--mut:#6b6b66;--line:#e3e2dc;--acc:#0b5cad}
@media(prefers-color-scheme:dark){:root{--bg:#161614;--fg:#e9e8e3;--mut:#9a9992;--line:#2e2e2a;--acc:#7db4ee}}
body{background:var(--bg);color:var(--fg);font:16px/1.75 -apple-system,"PingFang SC","Helvetica Neue",sans-serif;margin:0;padding:24px 16px 64px}
main{max-width:720px;margin:0 auto}h1{font-size:26px;line-height:1.3}h2{font-size:20px;margin-top:40px;border-bottom:1px solid var(--line);padding-bottom:6px}
h3{font-size:18px;line-height:1.45;margin-top:28px}a{color:var(--acc);text-decoration:none}a:hover{text-decoration:underline}
blockquote{margin:0;color:var(--mut)}hr{border:0;border-top:1px solid var(--line);margin:28px 0}code{color:var(--mut);font-size:13px}
details{color:var(--mut);font-size:14px}li{overflow-wrap:anywhere}</style></head><body><main id="m"></main>
<script src="https://cdnjs.cloudflare.com/ajax/libs/marked/12.0.2/marked.min.js"></script>
<script>document.getElementById("m").innerHTML=marked.parse(%s)</script></body></html>
"""


def wechat_text(md: str, link: str) -> str:
    """Section headers + numbered titles with score and original URL."""
    urls = dict(re.findall(r'<a id="(item-[\w-]+)"></a>\n### \[.*?\]\((\S+?)\)', md))
    title = md.splitlines()[0].lstrip("# ").replace(" - ", " ")
    count = re.search(r"^> (.+)$", md, re.M)
    out = [f"📰 {title}", count.group(1) if count else "", ""]
    toc = md.split("\n---\n")[1] if "\n---\n" in md else ""
    for line in toc.splitlines():
        if m := re.fullmatch(r"\*\*(.+)\*\*", line.strip()):
            out += [f"【{m.group(1)}】"]
        elif m := re.match(r"(\d+)\. \[(.+)\]\(#(item-[\w-]+)\) ⭐️ ([\d.]+)/10", line):
            n, name, anchor, score = m.groups()
            out += [f"{n}. {name}（{score}）", html.unescape(urls.get(anchor, "")), ""]
    footer = f"完整版（含背景、验证、讨论）：{link}"
    body = "\n".join(out)
    # ponytail: hard truncation; split into several messages if digests outgrow one
    return body[: WECHAT_LIMIT - len(footer) - 2].rstrip() + "\n\n" + footer


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    root = Path(__file__).resolve().parent.parent
    path = Path(args[0]) if args else max((root / "data/summaries").glob("horizon-*-zh.md"))
    md = path.read_text(encoding="utf-8")
    title = md.splitlines()[0].lstrip("# ").replace(" - ", " ")

    tmp = Path(tempfile.mkdtemp())
    page = tmp / (path.stem + ".html")
    # "</" would end the inline <script> early
    page.write_text(PAGE % (html.escape(title), json.dumps(md).replace("</", "<\\/")), encoding="utf-8")
    shared = subprocess.run([str(SHARE), "publish", str(page)], check=True, capture_output=True, text=True).stdout
    link = re.search(r"https://share\.outman\.cc/share/\w+", shared).group(0)
    print(link)

    txt = tmp / "wechat.txt"
    txt.write_text(wechat_text(md, link), encoding="utf-8")
    print(txt, len(txt.read_text(encoding="utf-8")), "chars")
    if "--no-send" not in sys.argv:
        subprocess.run(["hermes", "send", "--to", "weixin", "--file", str(txt)], check=True)


if __name__ == "__main__":
    main()
