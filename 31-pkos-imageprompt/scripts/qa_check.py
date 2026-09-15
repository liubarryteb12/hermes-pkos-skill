#!/usr/bin/env python3
"""31-imageprompt 题词机械校验（智力脱钩补强 ② + v1.4.0 成品标准）。

两种模式：
  --pack <file>      校验单个题词包（六段命名 + 五键 + S00 + 参数）
  --library [DIR]    逐条校验题词库条目是否符合 v1.4.0「成品标准」
                     （默认校验套件内 references/prompt-library）

用法:
  python qa_check.py --pack out.md
  python qa_check.py --library
  python qa_check.py --library D:/00.AIagent/hermesagent/workspace/modelscope-prompts
"""
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LIB = ROOT / "references" / "prompt-library"

SIX_SEG = re.compile(r"\bM\d{2}-S\d{2}(?:-\d{1,2})?\b")  # 母题-子题(-系列Xxx)成对出现；六段 M-S-X-F-U-A
PARAM_KEYS = ("分辨率", "比例", "画幅", "resolution", "aspect", "size")
# S00 安全层：直白敏感词（出现即拒——表达必须升维，不靠藏词）
NSFW_RAW = re.compile(
    r"(nude|naked|nsfw|裸体|全裸|半裸|乳头|乳沟特写|生殖器|做爱|性交|援交)"
    r"|(未成年|青[0-9]{0,2}岁|幼[女儿]|萝莉|loli|小学生?体)",
    re.I)
# S00-v2 标准档专属词族：氛围/挑逗词 + 恋物材质枚举。标准档（M01-M04）出现即拒；
# M05 性张力系列宽松档放行（用户 09-14 裁定），硬红线不在此列、照扫。
STD_ONLY = re.compile(
    r"(性感|妩媚|诱惑|妖娆|sultry|seductive|teasing|provocative"
    r"|see-through|透肤|denier|nylon weave)", re.I)

# ── v1.4.0 成品标准 ────────────────────────────────────────────────
MIN_LEN = 120          # 条目正文字符数下限（人像类建议 180-300）
ENTRY_RE = re.compile(
    r"^\s*\d+\.\s*`?(M\d{2}-S\d{2}-\d{1,3}-F\d{2}-U\d{2}-A\d{2}[^`\s]*)`?\s+(.+?)\s*$")
FIG_RE = re.compile(r"\d+\s*[:：]\s*\d+(?:\.\d+)?")           # 画幅 9:16 / 4:5 / 2.35:1
LIGHT_KW = ("光", "light", "晨", "暮", "阳光", "灯", "逆光", "柔光", "直闪",
            "散射", "high-key", "low-key", "bloom", "照明", "烛", "月",
            # 插画/平面类的明暗语汇（无摄影光源时用光影/明暗/着色策略表达）
            "光影", "明暗", "高光", "暗部", "辉光", "glow", "shading", "cel", "平涂", "套色")
CAM_KW = ("mm", "镜头", "机位", "景深", "虚化", "构图", "焦点", "视角", "透视",
          "俯拍", "仰拍", "焦段", "depth of field", "lens", "长焦", "广角",
          # 平面/插画类的版式语汇 + 中文景别词（M05 套图常用）
          "版式", "排版", "留白", "景别", "构成", "布局", "卡面", "画角",
          "特写", "半身", "全身", "剪影", "过肩", "低机位", "高机位", "平视", "中景", "远景", "近景")
TEX_KW = ("质感", "材质", "颗粒", "纹理", "grain", "tone", "色调", "色彩", "色温",
          "grading", "皮肤", "缎", "棉", "针织", "纸", "金属", "漆", "布")
MOOD_KW = ("情绪", "氛围", "气质", "安静", "松弛", "静谧", "慵懒", "克制", "空灵",
           "清冷", "温暖", "怀旧", "张力")
ADULT_RE = re.compile(r"成年")
# 条目是否出现人物/人体局部——「成年」锚点只对这些条目强制（S00 原意：人像类）
NEG_PERSON = re.compile(r"不出现(人物|面部|人脸)|无(人物|面部)|不含人物|无面部|不露脸")
# 注意：不含「角色/人物」——本库中它们是归属/题材词（如「角色鞋履…无面部构图稿」），不表示画面出现人体
PERSON_RE = re.compile(r"她|他|女性|男性|模特|人像|半身|头像|身影|剪影|背影|姿态|"
                       r"手部|手指|指节|手背|指尖|手腕|手掌|手臂|一只手|双手|的手|脚|脚踝|脚尖|足|腿|肩|颈|脸|面部|眼睛|皮肤|头发|发丝")
PANEL_HINT = re.compile(r"分屏|并排|turnaround|正背|多格|拼贴|九宫格|四格|三格|两格|上下两")
PANEL_MARK = re.compile(r"\[[0-9一二三四五六七八九十]+\s*格")
PLACEHOLDER = re.compile(r"【待补|TODO(?!S?)|占位框|<xxx>")
# 需要「成年」锚点的子题前缀（人像/真人向）
ADULT_PREFIXES = ("M01-", "M02-S01", "M02-S02", "M02-S04", "M05-")


def check(text: str) -> list[str]:
    """单题词包校验（--pack 模式，保持 v1.3 行为不变）。"""
    errors = []
    # 1. 命名：至少一处 Mxx-Sxx 锚（六段码 M-S-X-F-U-A）
    if not SIX_SEG.search(text):
        errors.append("缺命名锚（Mxx-Sxx 至少成对；完整六段 M-S-X-F-U-A 见 00-总览）")
    # 2. 五键结构（code/positive/negative/anchor/params 任一种书写形态）
    keys_present = sum(bool(re.search(rf"{k}\s*[:：]", text, re.I))
                       for k in ("code", "positive", "negative", "anchor", "params"))
    if keys_present < 3:
        errors.append(f"题词包五键缺失（仅识别到 {keys_present}/5：code/positive/negative/anchor/params）")
    # 3. negative 必须存在且非空（ModelScope 正负两框都全文审核）
    neg = re.search(r"negative\s*[:：]\s*(\S.{0,120})", text, re.I)
    if not neg or len(neg.group(1).strip()) < 4:
        errors.append("negative 缺失或过短（S00：正负两框都要写全）")
    # 4. 出图参数在位（C00：提示词必配参数）
    if not any(k.lower() in text.lower() for k in PARAM_KEYS):
        errors.append("缺出图参数（分辨率/比例/画幅任一，C00 规范）")
    # 5. S00 安全扫描（正向+负向全文，直白词零容忍）
    m = NSFW_RAW.search(text)
    if m:
        errors.append(f"S00 安全层拒绝：直白敏感表述 '{m.group(0)[:20]}'（须表达升维，改用光影/构图/氛围词）")
    # 6. 占位符
    if PLACEHOLDER.search(text):
        errors.append("题词含占位符")
    return errors


def check_entry(code: str, body: str, fname: str, section: str | None = None,
                lenient: bool = False) -> tuple[list[str], list[str]]:
    """lenient=True 时跳过 S00 直白词扫描（M05 性张力系列宽松档，S00-v2 双档制），
    成年锚点/长度/画幅/光线/镜头/分格/编号检查照常；硬红线词（未成年/数字参数）仍扫。"""
    """单条目成品标准校验（v1.4.1）。返回 (硬错误, 软提示)。

    ④质感/⑤情绪 降级为软提示：二者无法机械判定，而「必须出现字面词」的硬规则
    会反向逼迫作者写出模板化句子（曾导致 320/320 条目以「情绪X、Y」收尾）。
    硬门禁只保留可机械判定的项：长度/画幅/光线/镜头/成年锚点/分格标记/编号/安全。
    """
    errs, softs = [], []
    if len(body) < MIN_LEN:
        errs.append(f"过短：{len(body)} 字 < {MIN_LEN}（成品标准：完整可粘贴提示词）")
    if not FIG_RE.search(body):
        errs.append("缺画幅数字（Uxx/C00 三处一致）")
    if not any(k.lower() in body.lower() for k in LIGHT_KW):
        errs.append("缺光线描述（成品标准五要素②）")
    if not any(k.lower() in body.lower() for k in CAM_KW):
        errs.append("缺镜头/构图语言（成品标准五要素③）")
    if not (any(k.lower() in body.lower() for k in TEX_KW)
            or any(k.lower() in body.lower() for k in MOOD_KW)):
        softs.append("未见显式质感/情绪词（五要素④⑤ 为软提示，写具体体态/氛围亦可）")
    if fname.startswith(ADULT_PREFIXES) and PERSON_RE.search(NEG_PERSON.sub("", body)) and not ADULT_RE.search(body):
        errs.append("缺「成年」锚点（S00 硬性要求：条目出现人物/人体局部时必写）")
    if PANEL_HINT.search(body) and not PANEL_MARK.search(body):
        errs.append("疑似分格图但未标格数布局（单图/分格判定：须写 [N格 布局]）")
    # 硬红线（裸露直白词/未成年词）对所有系列恒扫，永不放宽
    m = NSFW_RAW.search(body)
    if m:
        errs.append(f"S00 硬红线：'{m.group(0)[:20]}'")
    # 标准档词族（氛围词/恋物材质枚举）仅 M01-M04 机械拦截；M05 宽松档放行（S00-v2 双档制）
    if not lenient:
        m2 = STD_ONLY.search(body)
        if m2:
            errs.append(f"S00 标准档拒绝（M05 宽松档可放行）：'{m2.group(0)[:16]}'")
    if PLACEHOLDER.search(body):
        errs.append("含占位符")
    if section:
        mf = re.match(r"M\d{2}-S\d{2}-\d{1,2}-(F\d{2})-", code)
        if mf and mf.group(1) != section:
            errs.append(f"编号 Fxx({mf.group(1)}) 与所在章节 {section} 不一致")
    return errs, softs


SEC_HEAD = re.compile(r"^##\s+(F\d{2})\b")


def check_library(lib: Path) -> dict:
    files = sorted(lib.glob("M*-S*-*-*.md"))
    errors, warnings, softs = [], [], []
    seen: dict[str, str] = {}
    per_file: dict[str, int] = {}
    total = 0
    for f in files:
        txt = f.read_text(encoding="utf-8", errors="ignore")
        cnt = 0
        sec = None
        for lineno, line in enumerate(txt.splitlines(), 1):
            sh = SEC_HEAD.match(line)
            if sh:
                sec = sh.group(1)
                continue
            m = ENTRY_RE.match(line)
            if not m:
                continue
            code, body = m.group(1), m.group(2)
            cnt += 1
            total += 1
            if code in seen:
                errors.append(f"{f.name}:{lineno} 编号重复 {code}（已见于 {seen[code]}）")
            else:
                seen[code] = f"{f.name}:{lineno}"
            e_list, s_list = check_entry(code, body, f.name, lenient=f.name.startswith("M05"))
            errors += [f"{f.name}:{lineno} {code} — {e}" for e in e_list]
            softs += [f"{f.name}:{lineno} {code} — {s}" for s in s_list]
        per_file[f.name] = cnt
        if cnt == 0:
            warnings.append(f"{f.name}: 未解析到任何条目（格式漂移？）")
    return {
        "ok": not errors,
        "total_entries": total,
        "files": len(files),
        "per_file": per_file,
        "errors": errors,
        "warnings": warnings,
        "soft_notes": softs[:40],
        "soft_count": len(softs),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="31-imageprompt 题词校验（六段命名+S00+参数 / v1.4.0 成品标准）")
    ap.add_argument("--pack", help="单题词包文件")
    ap.add_argument("--file", help="校验单个题词库文件（逐条成品标准）")
    ap.add_argument("--library", nargs="?", const=str(DEFAULT_LIB), default=None,
                    help="逐条校验题词库（可给目录，默认套件内 references/prompt-library）")
    ap.add_argument("--quiet", action="store_true", help="只输出统计与首 20 条错误")
    a = ap.parse_args()

    if a.file:
        f = Path(a.file)
        if not f.is_file():
            print(json.dumps({"ok": False, "errors": [f"文件不存在：{f}"]}, ensure_ascii=False))
            return 2
        txt = f.read_text(encoding="utf-8", errors="ignore")
        errors, n, softs = [], 0, []
        sec = None
        for lineno, line in enumerate(txt.splitlines(), 1):
            sh = SEC_HEAD.match(line)
            if sh:
                sec = sh.group(1)
                continue
            m = ENTRY_RE.match(line)
            if not m:
                continue
            n += 1
            e_list, s_list = check_entry(m.group(1), m.group(2), f.name, sec, lenient=f.name.startswith("M05"))
            errors += [f"{f.name}:{lineno} {m.group(1)} — {e}" for e in e_list]
            softs += [f"{f.name}:{lineno} {m.group(1)} — {s}" for s in s_list]
        print(json.dumps({"ok": not errors, "file": f.name, "entries": n, "errors": errors,
                          "soft_notes": softs[:40], "soft_count": len(softs)},
                         ensure_ascii=False, indent=2))
        return 0 if not errors else 1

    if a.library:
        lib = Path(a.library)
        if not lib.is_dir():
            print(json.dumps({"ok": False, "errors": [f"目录不存在：{lib}"]}, ensure_ascii=False))
            return 2
        r = check_library(lib)
        if a.quiet:
            r["errors"] = r["errors"][:20]
            r["per_file"] = {k: v for k, v in r["per_file"].items()}
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return 0 if r["ok"] else 1

    if a.pack:
        text = Path(a.pack).read_text(encoding="utf-8-sig", errors="ignore")
        errors = check(text)
        print(json.dumps({"ok": not errors, "errors": errors}, ensure_ascii=False))
        return 1 if errors else 0

    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
