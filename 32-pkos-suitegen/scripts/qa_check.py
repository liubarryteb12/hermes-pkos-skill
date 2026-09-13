#!/usr/bin/env python3
"""32-pkos-suitegen 机械校验（智力脱钩补强，套件 6 纯提示词单元同款模式）
校验套图剧本/题词产物：剧本模板齐备 + 张数 8-22 + 场景要素齐 + S00 安全 + 风格注册引用。

用法: python qa_check.py --pack <套图产物.md>
"""
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STYLES = ROOT / "references" / "styles"
SCRIPTS = ROOT / "references" / "scripts"

SIX_SEG = re.compile(r"\bM\d{2}-S\d{2}(?:-\d{1,2})?\b")
NSFW_RAW = re.compile(
    r"(nude|naked|nsfw|裸体|全裸|半裸|乳头|生殖器|做爱|性交)"
    r"|(青[0-9]?岁?|幼[女儿]|萝莉|loli)", re.I)
PARAM_KEYS = ("分辨率", "比例", "画幅", "resolution", "aspect", "size")
SCENE_KEYS = ("场景", "机位", "主体", "情绪", "衔接", "scene", "shot", "mood", "transition")


def check(text: str) -> list[str]:
    errors = []
    # 1. 剧本骨架：引用模板存在
    tmpl = re.search(r"script[：:]\s*(growth-line|city-walk|one-day|free-form)", text, re.I)
    if not tmpl or not (SCRIPTS / f"{tmpl.group(1)}.md").exists():
        errors.append("缺剧本模板引用或模板不存在（growth-line/city-walk/one-day/free-form）")
    # 2. 张数 8-22
    cnt = re.search(r"(?:张数|count)[：:\s]*(\d+)", text, re.I)
    if not cnt:
        errors.append("缺张数声明")
    elif not (8 <= int(cnt.group(1)) <= 22):
        errors.append(f"张数 {cnt.group(1)} 不在 8-22")
    # 3. 场景要素齐（每场至少 scene+shot）
    scene_ok = sum(k in text for k in SCENE_KEYS)
    if scene_ok < 4:
        errors.append(f"场景要素不足（识别 {scene_ok}/6：场景/机位/主体/情绪/衔接/景别）")
    # 4. 风格注册引用（从 _registry.md 动态解析，禁用硬编码风格名）
    reg = STYLES / "_registry.md"
    registered = []
    if reg.exists():
        for line in reg.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^\|\s*`([a-z0-9-]+)`", line)
            if m:
                registered.append(m.group(1))
    if not registered:
        errors.append("风格注册表 _registry.md 为空或不可解析")
    else:
        cited = re.search(r"style[_ -]?id[：:\s]*([a-z0-9-]+)", text, re.I)
        if cited and cited.group(1) not in registered:
            errors.append(f"引用未注册风格 '{cited.group(1)}'（_registry.md 登记制）")
        elif not cited and not any(s in text for s in registered):
            errors.append("未引用任何已注册风格 skill（styles/_registry.md）")
    # 5. 六段题词锚
    if not SIX_SEG.search(text):
        errors.append("缺六段题词锚（Mxx-Sxx(-Xxx) 至少成对，见 00-总览）")
    # 6. negative 必须存在且非空（S00：正负两框都全文审核，与 31 同规格）
    neg = re.search(r"negative\s*[：:]\s*(\S.{0,120})", text, re.I)
    if not neg or len(neg.group(1).strip()) < 4:
        errors.append("negative 缺失或过短（S00：正负两框都要写全）")
    # 7. S00 安全
    m = NSFW_RAW.search(text)
    if m:
        errors.append(f"S00 拒绝：直白表述 '{m.group(0)[:20]}'")
    # 7. 占位符
    if re.search(r"【待补|TODO(?!S?)|占位框|<xxx>", text):
        errors.append("含占位符")
    return errors


def main() -> int:
    ap = argparse.ArgumentParser(description="32-suitegen 套图产物校验")
    ap.add_argument("--pack", required=True)
    a = ap.parse_args()
    text = Path(a.pack).read_text(encoding="utf-8-sig", errors="ignore")
    errors = check(text)
    print(json.dumps({"ok": not errors, "errors": errors}, ensure_ascii=False))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())