#!/usr/bin/env python3
"""把 data.json 塞進 template.html，產生 site/index.html（GitHub Pages 發布用）。"""
import os
H = os.path.dirname(os.path.abspath(__file__))
data = open(os.path.join(H, "data.json")).read().replace("</", "<\\/")
body = open(os.path.join(H, "template.html")).read().replace("__DATA__", data)
html = ('<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
        '<style>:root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}'
        'body{margin:0}img{max-width:100%}[hidden]{display:none!important}</style></head><body>'
        + body + '</body></html>')
os.makedirs(os.path.join(H, "site"), exist_ok=True)
open(os.path.join(H, "site", "index.html"), "w").write(html)
print("built site/index.html", len(html) // 1024, "KB")
