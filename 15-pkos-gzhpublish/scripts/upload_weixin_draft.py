# -*- coding: utf-8 -*-
"""上传参考图 + 发送带图 prompt：用 opencli upload 上传定妆照，再注入文字 prompt 发送。
用法: python comic_upload_send.py <ref_image> <prompt_file> <out_name>
"""
import base64
import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path

OCLI_DIR = Path.home() / "AppData/Local/OpenCLIApp/node_modules/@jackwener/opencli/dist/src/main.js"
ARCH = Path(r"D:/00.AIagent/hermesagent/pkos-outputs/comic/images")


def oc(*args, timeout=120):
    r = subprocess.run(["node", str(OCLI_DIR), "--profile", "5d5kre8b", "browser",
                        "gemini-comic", *args],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    return r.stdout


def ev(js, timeout=120):
    return oc("eval", js, timeout=timeout)


def blob_count():
    m = re.search(r'"n":\s*(\d+)', ev('(() => { const big=[...document.querySelectorAll("img")]'
                                      '.filter(i=>i.naturalWidth>400&&i.naturalHeight>400&&i.src.startsWith("blob:"));'
                                      'return JSON.stringify({n: big.length}); })()'))
    return int(m.group(1)) if m else 0


def send_text(prompt):
    esc = json.dumps(prompt, ensure_ascii=False)
    inj = ("(() => { const el=document.querySelector(\"div[contenteditable='true']\");"
           " if(!el) return 'no-input'; el.focus();"
           " document.execCommand('insertText', false, " + esc + "); return 'injected'; })()")
    if "injected" not in ev(inj):
        return False
    time.sleep(2)
    for _ in range(30):
        ev('(() => { const b=document.querySelector(\'button[aria-label="Send message"]\');'
           ' if(b && !b.disabled){ b.click(); return "clicked"; } return "wait"; })()')
        time.sleep(1.5)
        m = re.search(r'"len":\s*(-?\d+)',
                      ev('(() => { const ed=document.querySelector("div[contenteditable=true]");'
                         ' return JSON.stringify({len: ed?ed.textContent.length:-1}); })()'))
        if m and int(m.group(1)) == 0:
            return True
    return False


def wait_user_bubble(keyword, timeout_s=90):
    """发送成功的可靠信号：页面出现含 keyword 的用户气泡"""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        time.sleep(4)
        raw = ev("(() => { const r=document.querySelector('chat-app');"
                 " const t=r?r.innerText:document.body.innerText;"
                 " return JSON.stringify({has: t.includes(" + json.dumps(keyword) + "), pagelen:t.length}); })()")
        m = re.search(r'"has":\s*(true|false)', raw)
        if m and m.group(1) == "true":
            pm = re.search(r'"pagelen":\s*(\d+)', raw)
            return int(pm.group(1)) if pm else 0
    return -1


def wait_new_image(base_n, max_s=300):
    deadline = time.time() + max_s
    while time.time() < deadline:
        time.sleep(10)
        if blob_count() > base_n:
            return True
    return False


def grab_last(dst):
    js = ('(() => new Promise(res => { const imgs=[...document.querySelectorAll("img")]'
          '.filter(i=>i.naturalWidth>400&&i.naturalHeight>400&&i.src.startsWith("blob:"));'
          'const img=imgs[imgs.length-1];'
          'if(!img) return res(JSON.stringify({err:"no-img"}));'
          'const c=document.createElement("canvas"); c.width=img.naturalWidth; c.height=img.naturalHeight;'
          'const ctx=c.getContext("2d"); ctx.drawImage(img,0,0);'
          'try { const d=c.toDataURL("image/jpeg",0.92);'
          'res(JSON.stringify({ok:true, data:d.slice(d.indexOf(",")+1), w:img.naturalWidth, h:img.naturalHeight}));}'
          'catch(e){ res(JSON.stringify({err:e.message})); } }))()')
    out = ev(js, timeout=120)
    i, j = out.find("{"), out.rfind("}")
    if i < 0:
        return None
    d = json.loads(out[i:j + 1])
    if d.get("ok"):
        raw = base64.b64decode(d["data"])
        dst.write_bytes(raw)
        return {"bytes": len(raw), "size": f'{d["w"]}x{d["h"]}'}
    return None


def main():
    ref_img, prompt_file, name = sys.argv[1], sys.argv[2], sys.argv[3]
    prompt = Path(prompt_file).read_text(encoding="utf-8").strip()
    keyword = prompt[:24]

    # 上传参考图
    up = oc("upload", str(Path(ref_img).resolve()), timeout=120)
    if "uploaded" not in up.lower() and "success" not in up.lower():
        print("UPLOAD_CHECK:", up[:200])
    time.sleep(3)

    # 发送文字
    if not send_text(prompt):
        print("SEND_FAIL")
        return 1

    # 验证用户气泡出现（确认发出）
    pl = wait_user_bubble(keyword)
    if pl < 0:
        print("BUBBLE_TIMEOUT (可能已发出，继续等图)")
    base_n = blob_count()
    if not wait_new_image(base_n):
        print("GEN_TIMEOUT")
        return 1
    time.sleep(4)
    dst = ARCH / name
    info = grab_last(dst)
    if info:
        dst.with_suffix(".manifest.json").write_text(json.dumps({
            "file": name, "via": "canvas-blob", "ref": Path(ref_img).name,
            "bytes": info["bytes"], "size": info["size"],
            "sha256_12": hashlib.sha256(dst.read_bytes()).hexdigest()[:12],
            "ts": time.strftime("%Y-%m-%d %H:%M:%S")}, ensure_ascii=False, indent=1),
            encoding="utf-8")
        print(f"SAVED {dst} {info['size']} {info['bytes']//1024}KB")
        return 0
    print("GRAB_FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
