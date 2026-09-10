#!/usr/bin/env python3
"""00-pkos-init/scripts/bootstrap.py — 对话式初始化（09-10 用户裁定）。

两种用法：
  A) agent 引导模式（推荐）：agent 依次问用户 3 个问题（vault/workspace/收件箱），
     然后以参数调用本脚本完成配置生成 + 目录骨架 + 自检：
       python bootstrap.py --vault "<路径>" --workspace "<路径>" [--inbox "<路径>" ...] [--create-vault]
  B) 自检模式：python bootstrap.py --check   （读现有 config，逐项校验，exit 0 = 就绪）

行为：
  - vault 已存在 → 直接用；不存在且 --create-vault → 建编号域制骨架；否则拒绝（防手滑建错地方）
  - workspace 不存在 → 自动创建（产物目录，低风险）
  - inbox 不存在且在 vault 内 → 自动创建；vault 外的不存在 → 拒绝（提醒用户确认）
  - LLM 网关：走 Hermes 自身配置，本脚本不做任何网关配置（设计边界，09-10 用户拍板）
  - 生成 <套件根>/config.json（schema pkos-config:1），此后全部单元经 pkos_paths 读路径
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))
import pkos_paths

VAULT_SKELETON = ["_PKOS/INBOX", "_PKOS/manifests", "_PKOS/handoffs", "_PKOS/reports",
                  "01-收件箱", "02-知识条目", "03-出口产物", "90-归档"]


def ensure_dir(p: Path, what: str, create: bool) -> list[str]:
    if p.is_dir():
        return []
    if not create:
        raise NotADirectoryError(f"{what} 不存在且未允许创建: {p}")
    p.mkdir(parents=True, exist_ok=True)
    return [f"created:{p}"]


def main() -> int:
    ap = argparse.ArgumentParser(description="PKOS 对话式初始化（生成 config.json + 目录骨架）")
    ap.add_argument("--vault", help="知识库根目录（已有库直接指；新建需配 --create-vault）")
    ap.add_argument("--workspace", help="workspace：出口产物落点（不存在会自动创建）")
    ap.add_argument("--inbox", action="append", default=None,
                    help="收件箱目录（可多次；缺省 = <vault>/_PKOS/INBOX）")
    ap.add_argument("--create-vault", action="store_true", help="vault 不存在时创建编号域制骨架")
    ap.add_argument("--check", action="store_true", help="自检现有配置")
    a = ap.parse_args()

    # ---- 自检模式 ----
    if a.check:
        cfg = pkos_paths._load()
        from_config = pkos_paths.config_exists()
        problems = []
        vault = pkos_paths.get_vault()
        if not vault.is_dir():
            problems.append(f"vault 不存在: {vault}")
        ws = pkos_paths.get_workspace()
        if not ws.is_dir():
            problems.append(f"workspace 不存在: {ws}")
        for ib in pkos_paths.get_inboxes():
            if not ib.is_dir():
                problems.append(f"收件箱不存在: {ib}")
        print(json.dumps({
            "ok": not problems, "config_file": str(pkos_paths.CONFIG_PATH),
            "from_config": from_config, "vault": str(vault), "workspace": str(ws),
            "inboxes": [str(x) for x in pkos_paths.get_inboxes()],
            "problems": problems,
            "note": "LLM 网关走 Hermes 自身配置，无需在此设置",
        }, ensure_ascii=False, indent=1))
        return 1 if problems else 0

    # ---- 初始化模式 ----
    missing = [name for name, v in (("vault", a.vault), ("workspace", a.workspace)) if not v]
    if missing:
        print(json.dumps({"ok": False, "error": f"缺参数: {missing}",
                          "hint": "agent 引导用户依次提供 vault 与 workspace 后再调用"}, ensure_ascii=False))
        return 4

    actions: list[str] = []
    vault = Path(a.vault).resolve()
    created = ensure_dir(vault, "vault", a.create_vault)
    actions += created
    if created and "--create-vault" in sys.argv:
        for rel in VAULT_SKELETON:
            (vault / rel).mkdir(parents=True, exist_ok=True)
        actions.append(f"created-skeleton:{len(VAULT_SKELETON)} dirs")

    workspace = Path(a.workspace).resolve()
    actions += ensure_dir(workspace, "workspace", True)

    inboxes = [Path(x).resolve() for x in (a.inbox or [])]
    if not inboxes:
        inboxes = [vault / "_PKOS" / "INBOX"]
    for ib in inboxes:
        inside_vault = str(ib).startswith(str(vault))
        actions += ensure_dir(ib, "收件箱", create=inside_vault)

    cfg_path = pkos_paths.write_config(str(vault), str(workspace), [str(x) for x in inboxes])

    # 写后自检
    problems = []
    if not vault.is_dir(): problems.append(f"vault 不存在: {vault}")
    if not workspace.is_dir(): problems.append(f"workspace 不存在: {workspace}")
    print(json.dumps({
        "ok": not problems, "config_file": str(cfg_path),
        "vault": str(vault), "workspace": str(workspace),
        "inboxes": [str(x) for x in inboxes],
        "actions": actions, "problems": problems,
        "next": ["各单元脚本自动从 config.json 读路径（未初始化环境回退内置默认）",
                 "LLM 网关走 Hermes 自身配置，无需额外设置"],
    }, ensure_ascii=False, indent=1))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
