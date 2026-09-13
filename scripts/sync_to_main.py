#!/usr/bin/env python3
"""sync_to_main.py — Hermes live 包 → 发布主库 目录级全量同步（v2，09-09 重写）。

根因教训：v1 是固定文件清单（CORE_FILES），新单元/新文件不在清单内就永远漏同步
（09-06~08 另一会话加的 4 单元、09-09 gemini-image 修复全被漏掉）。v2 改为全树 md5 比对。

规则：
  方向：live → main 单向（SSOT = Hermes live 包）。
  排除（两边都不碰）：_PKOS/ _trash/ _ops/ cn_debug/ .git/ .code-review-graph/
                     __pycache__/ .pytest_cache/ *.md.build  reports/（skillopt 训练证据单独白名单）。
                     _ops/ 与 cn_debug/ 为本机操作文件与调试现场，不进发布主库。
  main-only 发布件保留不删：README.md LICENSE INSTALL 之外的 docs 发布件（FAQ/sponsor/
                     MIGRATION/EVOLUTION-DECISIONS/OPERATOR-DECISIONS/PITFALLS 等）、
                     12-pkos-comic/references/ 若 main 独有亦保留（发布面资产）。
  IP 净化：写入 main 时网关 IP → <LLM_GATEWAY_HOST>（发布红线）。
用法：python scripts/sync_to_main.py --check   # 只报告漂移（exit 1=有漂移）
     python scripts/sync_to_main.py --apply   # 同步 + 净化 + 复核
"""
from __future__ import annotations
import hashlib
import os
import os
import shutil
import sys
from pathlib import Path

LIVE = Path(os.environ.get("PKOS_SYNC_LIVE", Path(__file__).resolve().parents[1]))
MAIN = Path(r"D:\00.AIagent\pkos\skills\personal-knowledge-os")

EXCLUDE_PARTS = {"_PKOS", "_trash", ".git", "__pycache__", ".pytest_cache",
                 ".code-review-graph", ".tmp", ".tmp-test",
                 # 09-14 迁移：操作文件区（脚本/状态快照/日志）与调试现场均为本机资产，
                 # 随套件本体留在 live，不进发布主库（对应 .gitignore 的 _ops/）
                 "_ops", "cn_debug"}
EXCLUDE_SUFFIX = {".build", ".pptx", ".pyc"}
# live 下 reports/ 仅 skillopt 训练证据参与同步
SYNC_REPORTS = {"23-pkos-skillopt"}
# main 独有、永不删除的发布面文件（相对 main 前缀匹配）
MAIN_KEEP = ("README.md", "LICENSE", "docs/FAQ.md", "docs/sponsor-wechat.jpg",
             "docs/MIGRATION-5.0.md", "docs/EVOLUTION-DECISIONS.md", "docs/OPERATOR-DECISIONS.md",
             "docs/PITFALLS.md", "docs/lh-task-01-bootstrap.md",
             "23-pkos-skillopt/reports/skillopt/")
# live 版硬编码（live 不发布）；main 发布版用 PKOS_GATEWAY_IP 环境变量（未设则 SKIP 净化）
GATEWAY_IP = os.environ.get("PKOS_GATEWAY_IP", "<LLM_GATEWAY_HOST>")
GATEWAY_PLACEHOLDER = "<LLM_GATEWAY_HOST>"
TEXT_EXTS = {".md", ".py", ".json", ".yaml", ".yml", ".txt", ".ini", ".sql"}


def relfiles(base: Path) -> dict[str, Path]:
    out = {}
    for p in base.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(base)
        if any(s in rel.parts for s in EXCLUDE_PARTS):
            continue
        if rel.suffix in EXCLUDE_SUFFIX:
            continue
        # reports/ 目录：live 侧仅 skillopt 白名单；main 侧只留 main-only 发布件
        if "reports" in rel.parts:
            unit = rel.parts[0]
            if unit not in SYNC_REPORTS:
                continue
        out[str(rel).replace("\\", "/")] = p
    return out


def _norm(p: Path) -> bytes:
    raw = p.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    # 行尾归一：CRLF/CR -> LF。Windows(Python write_text) 与 Linux/echo 写盘行尾不同，
    # 不归一则同一文件会被判成「内容漂移」（09-14 VERSION/registry 假阳性根因）。
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def md5(p: Path) -> str:
    return hashlib.md5(_norm(p)).hexdigest()


def sanitize(text: str) -> str:
    """本机路径脱敏（用户名绝不入发布库）。

    用户名从 Path.home() 动态取——禁止硬编码进源码，否则脱敏正则本身
    就把本机用户名带进公开仓库（09-14 发版隐私终扫抓到）。
    """
    import re as _re
    user = _re.escape(Path.home().name)
    # 通用正则：单/双反斜杠、正斜杠全覆盖（JSON 转义串也在内）
    text = _re.sub(rf"C:[/\\]+Users[/\\]+{user}[/\\]+AppData[/\\]+Local[/\\]+hermes[/\\]+skills[/\\]+note-taking[/\\]+hermes-pkos-skill",
                   "<PKOS_SKILL_ROOT>", text)
    text = _re.sub(rf"C:[/\\]+Users[/\\]+{user}[/\\]+AppData[/\\]+Local[/\\]+hermes", "<HERMES_APPDATA>", text)
    text = _re.sub(rf"C:[/\\]+Users[/\\]+{user}", "<LOCAL_HOME>", text)
    if not GATEWAY_IP:  # 空 IP 时严禁 replace（replace("", X) 会把每个字符间都插入占位符）
        return text
    return (text.replace(f"http://{GATEWAY_IP}:1519", f"http://{GATEWAY_PLACEHOLDER}:1519")
                .replace(GATEWAY_IP, GATEWAY_PLACEHOLDER))


def copy_with_sanitize(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.suffix in TEXT_EXTS:
        try:
            t = src.read_text(encoding="utf-8-sig")
            dst.write_text(sanitize(t), encoding="utf-8")
            return
        except UnicodeDecodeError:
            pass
    shutil.copy2(src, dst)


def main() -> int:
    apply = "--apply" in sys.argv
    check = "--check" in sys.argv
    if not (apply or check):
        print("用法: sync_to_main.py --check | --apply")
        return 4
    a, b = relfiles(LIVE), relfiles(MAIN)
    drift_new = sorted(set(a) - set(b))                      # main 缺
    drift_mod = sorted(k for k in set(a) & set(b) if md5(a[k]) != md5(b[k]))  # 内容异
    # main 多余：不在 live、不在 KEEP 白名单、非净化差异
    extra = []
    for k in sorted(set(b) - set(a)):
        if any(k.startswith(p.rstrip("/") + ("/" if not p.endswith("/") else "")) or k == p for p in MAIN_KEEP):
            continue
        extra.append(k)
    # 自指豁免：sync_to_main.py 本身允许 LIVE 默认值钉法差异（parents[1] vs pinned）
    # 净化差异豁免：live 含真 IP、main 含占位符且其余一致 → 合法差异不算漂移
    legit_ip_diff = []
    drift_mod = [k for k in drift_mod if k != "scripts/sync_to_main.py"]
    for k in list(drift_mod):
        if a[k].suffix not in TEXT_EXTS:
            continue  # 非文本/无扩展名（VERSION 等）：不得豁免，md5 不同即真漂移
        lt = a[k].read_text(encoding="utf-8-sig", errors="ignore")
        mt = b[k].read_text(encoding="utf-8-sig", errors="ignore")
        if sanitize(lt) == mt:
            # 净化豁免（IP 与本机路径统一）：live 原样属内部态，main 净化形=发布态，二者规范等价
            drift_mod.remove(k)
            legit_ip_diff.append(k)

    n = len(drift_new) + len(drift_mod)  # EXTRA=main 独有发布件，仅报告不判失败
    print(f"sync_to_main: live→main 漂移 {n} 处"
          f"（缺 {len(drift_new)} / 异 {len(drift_mod)} / 多 {len(extra)}；净化豁免 {len(legit_ip_diff)}）")
    for k in drift_new:
        print(f"  [NEW] {k[:80]}")
    for k in drift_mod:
        print(f"  [MOD] {k[:80]}")
    for k in extra:
        print(f"  [EXTRA(main独有,保留待人工)] {k[:80]}")
    if apply and (drift_new or drift_mod):
        for k in drift_new + drift_mod:
            copy_with_sanitize(a[k], MAIN / k)
            print(f"  [FIXED] {k[:80]}")
        # 复核
        a2, b2 = relfiles(LIVE), relfiles(MAIN)
        left = [k for k in set(a2) & set(b2) if md5(a2[k]) != md5(b2[k])
                and k != "scripts/sync_to_main.py"]
        left = [k for k in left if not (a2[k].suffix in TEXT_EXTS and
                sanitize(a2[k].read_text(encoding="utf-8-sig", errors="ignore")) ==
                b2[k].read_text(encoding="utf-8-sig", errors="ignore"))]
        print("  ✓ 复核一致" if not left else f"  ✗ 仍有差异: {left[:5]}")
        n = len(drift_new) + len(drift_mod) if left else 0
    return 1 if n else 0


if __name__ == "__main__":
    sys.exit(main())
