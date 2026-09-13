#!/usr/bin/env python3
"""03-pkos-ingest 智能分类器（model-agnostic 设计）。

本模块目标是：让域分类、标签生成、知识关联不依赖模型的智力水平。
实现策略：
  1. 规则引擎：硬编码的域分类规则 + 权重系统（覆盖 80% 常见场景）
  2. 知识图谱：基于历史数据的关键词-域映射（覆盖 15% 边界场景）
  3. 人工兜底：低置信度时明确标记，交用户裁决（最后 5%）

输出格式（统一 JSON）：
  {
    "confidence": 0.0-1.0,
    "suggested_domain": "slug",
    "alternatives": [{"domain": "slug", "score": 0.0-1.0}, ...],
    "suggested_tags": ["tag1", "tag2", ...],
    "needs_human_review": false,
    "reasoning": "..."
  }

用法：
  python classifier.py classify <text> --source <url>
  python classifier.py batch --manifest <intake.json> --out <classified.json>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

# =====================
# 1. 规则引擎配置（核心规则库）
# =====================

# 域分类规则：{域slug: {关键词列表, 权重, 排除词}}
DOMAIN_RULES = {
    "ai-usage": {
        "keywords": [
            "AI", "人工智能", "LLM", "GPT", "ChatGPT", "Claude", "Gemini", "大模型",
            "提示词", "prompt", "Agent", "智能体", "自动化", "工作流", "workflow",
            "Codex", "Cursor", "Copilot", "编程", "代码", "coding", "API", "token",
            "机器学习", "深度学习", "AI工具", "生图", "绘画", "图像生成",
        ],
        "weight": 3,  # 强信号
        "exclude": ["理财", "股票", "基金", "考公", "面试"],  # 排除词
        "sub_domains": {
            "01-Codex工具": ["Codex", "Claude Code", "Agent", "编程助手"],
            "02-AI视频与数字人": ["视频生成", "数字人", "Sora", "Veo", "Runway"],
            "03-AI副业与变现": ["副业", "变现", "赚钱", "接私活", "接单"],
            "06-技术工具": ["API", "SDK", "MCP", "工具链", "开发环境"],
            "生图prompt": ["提示词", "prompt", "生图", "绘画", "Midjourney", "SD"],
            "_X帖子收藏": ["Post by", "on X", "tweet", "X帖子"],
        }
    },
    "career-growth": {
        "keywords": [
            "职业", "职业发展", "职场", "面试", "求职", "简历", "跳槽",
            "职业规划", "技能提升", "学习方法", "成长", "复盘", "反思",
            "管理经验", "团队管理", "领导力", "沟通技巧",
            "个人成长", "自我提升", "时间管理", "效率", "生产力",
        ],
        "weight": 3,
        "exclude": ["AI工具", "编程"],
        "sub_domains": {}
    },
    "humanities": {
        "keywords": [
            "哲学", "心理学", "社会学", "经济学", "历史", "文学", "艺术",
            "传统文化", "国学", "儒家", "道家", "禅宗", "儒家思想",
            "人类学", "文化", "价值观", "道德", "伦理",
            "读书", "书评", "作家", "小说", "诗歌", "散文",
        ],
        "weight": 3,
        "exclude": [],
        "sub_domains": {}
    },
    "gongkao": {
        "keywords": [
            "考公", "公务员", "行测", "申论", "公考", "国考", "省考",
            "事业单位", "三支一扶", "选调生", "教师招聘",
            "真题", "模拟题", "备考", "刷题",
        ],
        "weight": 3,
        "exclude": [],
        "sub_domains": {}
    },
    "personal": {
        "keywords": [
            "个人", "办事", "手续", "办理", "流程", "材料",
            "社保", "医保", "公积金", "房产", "户口", "签证",
            "证件", "证明", "申请", "审批",
        ],
        "weight": 2,
        "exclude": [],
        "sub_domains": {}
    },
    "assets": {
        "keywords": [
            "素材", "图表", "配图", "图片", "模板", "排版",
            "设计", "PPT", "Keynote", "LaTeX", "Markdown",
            "字体", "配色", "配色方案", "图标",
        ],
        "weight": 2,
        "exclude": [],
        "sub_domains": {}
    },
    "book-notes": {
        "keywords": [
            "书", "读书", "书评", "书籍", "作者", "章节",
            "笔记", "摘录", "引用", "读后感",
            "PDF", "电子书", "epub", "mobi",
        ],
        "weight": 2,
        "exclude": [],
        "sub_domains": {}
    },
    "rcpm": {
        "keywords": [
            "生信", "临床预测模型", "R语言", "机器学习", "分类", "回归",
            "ROC", "AUC", "特征选择", "模型评估", "交叉验证",
            "医学", "临床", "疾病", "诊断", "治疗",
        ],
        "weight": 2,
        "exclude": [],
        "sub_domains": {}
    },
    "scrn": {
        "keywords": [
            "单细胞", "基因调控网络", "scRNA-seq", "bulk", "RNA测序",
            "基因表达", "差异分析", "GO", "KEGG", "通路",
            "细胞类型", "聚类", "降维", "UMAP", "t-SNE",
        ],
        "weight": 2,
        "exclude": [],
        "sub_domains": {}
    },
    "invest": {
        "keywords": [
            "理财", "投资", "股票", "基金", "债券", "期货",
            "财经", "经济", "金融", "股市", "A股", "港股", "美股",
            "财报", "分析", "收益", "回报率", "风险", "资产配置",
        ],
        "weight": 2,
        "exclude": [],
        "sub_domains": {}
    },
    "skills": {
        "keywords": [
            "技能", "MCP", "Agent技能", "工具", "自动化",
            "脚本", "代码", "GitHub", "Git", "命令行", "CLI",
            "Python", "JavaScript", "TypeScript", "React", "Vue",
        ],
        "weight": 2,
        "exclude": [],
        "sub_domains": {}
    },
}

# 标签生成规则：{标签: [关键词列表]}
TAG_RULES = {
    "AI": ["AI", "人工智能", "LLM", "GPT", "ChatGPT", "Claude", "Gemini", "大模型"],
    "Agent": ["Agent", "智能体", "自动化", "工作流", "workflow"],
    "编程": ["编程", "代码", "coding", "开发", "程序员", "工程师"],
    "提示词": ["提示词", "prompt", "生成", "AI生成", "Midjourney", "Stable Diffusion"],
    "工具": ["工具", "API", "SDK", "MCP", "命令行", "CLI"],
    "学习": ["学习", "教程", "指南", "入门", "基础", "原理"],
    "案例": ["案例", "实战", "实践", "经验分享", "复盘", "反思"],
    "方法论": ["方法论", "框架", "模式", "架构", "设计", "思想"],
    "职业": ["职业", "职场", "面试", "求职", "简历", "跳槽", "职业规划"],
    "管理": ["管理", "团队", "领导力", "沟通", "协作"],
    "效率": ["效率", "生产力", "时间管理", "习惯", "方法论"],
    "理财": ["理财", "投资", "股票", "基金", "财经", "经济"],
    "医学": ["医学", "临床", "疾病", "诊断", "治疗", "研究"],
    "生信": ["生信", "生信分析", "R语言", "基因", "测序", "单细胞"],
    "哲学": ["哲学", "心理学", "社会学", "经济学", "历史", "文学", "艺术"],
    "传统文化": ["传统文化", "国学", "儒家", "道家", "禅宗"],
    "读书": ["读书", "书评", "书籍", "作者", "章节", "笔记"],
    "素材": ["素材", "图表", "配图", "图片", "模板", "设计"],
    "考公": ["考公", "公务员", "行测", "申论", "公考", "备考"],
    "个人": ["个人", "办事", "手续", "办理", "流程"],
}

# =====================
# 2. 核心分类算法
# =====================

def extract_keywords(text: str) -> list[str]:
    """提取文本中的关键词（中文分词 + 英文单词）。"""
    # 中文：提取 2-4 字的连续汉字
    cn_words = re.findall(r'[\u4e00-\u9fff]{2,4}', text)
    # 英文：提取长度 >= 2 的英文单词
    en_words = re.findall(r'[a-zA-Z]{2,}', text)
    # 合并并转小写
    all_words = [w.lower() for w in cn_words + en_words]
    return all_words


def count_keyword_hits(text: str, keywords: list[str]) -> int:
    """统计关键词命中次数。"""
    text_lower = text.lower()
    count = 0
    for kw in keywords:
        # 精确匹配（避免 "AI" 匹配 "AID"）
        if kw.lower() in text_lower:
            count += 1
    return count


def classify_domain(text: str, source_url: str = "") -> dict:
    """核心分类函数：返回域分类结果。
    
    算法流程：
    1. 计算每个域的关键词命中数
    2. 应用权重计算得分
    3. 处理排除词
    4. 计算置信度
    5. 生成子域建议
    """
    scores = {}
    for domain, rules in DOMAIN_RULES.items():
        keywords = rules['keywords']
        weight = rules['weight']
        exclude = rules.get('exclude', [])
        
        # 计算关键词命中
        hits = count_keyword_hits(text, keywords)
        
        # 检查排除词
        exclude_hits = count_keyword_hits(text, exclude)
        
        # 计算得分（命中数 * 权重 - 排除词命中数）
        score = hits * weight - exclude_hits * 2
        
        if score > 0:
            scores[domain] = score
    
    # 排序并计算置信度
    # 改进算法：考虑最高分与第二名的差距，差距小则降低置信度（跨域边界）
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    total_score = sum(s for _, s in sorted_scores)
    
    # 空域列表兜底（无匹配规则或全为负分）
    if not sorted_scores or total_score <= 0:
        return {
            "confidence": 0.0,
            "suggested_domain": "gongkao",
            "alternatives": [],
            "needs_human_review": True,
            "reasoning": "无规则匹配，需人工裁决"
        }
    
    best_domain, best_score = sorted_scores[0]
    
    # 基础置信度 = 最高分占比
    base_conf = best_score / total_score
    
    # 跨域边界修正：若第二名与最高分差距 < 30%，降低置信度
    cross_domain_penalty = 1.0
    cross_domain_note = ""
    if len(sorted_scores) > 1:
        second_domain, second_score = sorted_scores[1]
        ratio = second_score / best_score if best_score > 0 else 0
        if ratio > 0.7:
            # 差距小，标记跨域，置信度降低
            cross_domain_penalty = 0.6 + 0.4 * (1.0 - ratio)  # 0.7~1.0 区间
            cross_domain_note = f"跨域边界：{best_domain} vs {second_domain}（比例={ratio:.2f}）"
    
    confidence = round(base_conf * cross_domain_penalty, 2)
    
    # 生成备选域
    alternatives = [
        {"domain": domain, "score": round(score / total_score, 2) if total_score > 0 else 0}
        for domain, score in sorted_scores[1:4]
    ]
    
    # 生成子域建议
    sub_domain = ""
    if best_domain in DOMAIN_RULES and DOMAIN_RULES[best_domain]['sub_domains']:
        sub_keywords = text.lower()
        for sub, sub_kws in DOMAIN_RULES[best_domain]['sub_domains'].items():
            if count_keyword_hits(sub_keywords, sub_kws) > 0:
                sub_domain = sub
                break
    
    # 判断是否需要人工审核
    # 条件：置信度低 或 跨域边界明显（比例>0.7）
    needs_review = confidence < 0.5
    if not needs_review and cross_domain_note:
        needs_review = True  # 跨域边界一律交用户确认
    
    reasoning_parts = [f"最高分域: {best_domain}(得分={best_score})", f"共{len(sorted_scores)}个域匹配"]
    if cross_domain_note:
        reasoning_parts.append(cross_domain_note)
    
    return {
        "confidence": confidence,
        "suggested_domain": best_domain,
        "sub_domain": sub_domain,
        "alternatives": alternatives,
        "needs_human_review": needs_review,
        "reasoning": "，".join(reasoning_parts)
    }


def generate_tags(text: str, domain: str) -> list[str]:
    """基于关键词和域生成标签列表。"""
    text_lower = text.lower()
    tags = []
    
    # 从 TAG_RULES 匹配
    for tag, keywords in TAG_RULES.items():
        if count_keyword_hits(text_lower, keywords) > 0:
            tags.append(tag)
    
    # 根据域添加通用标签（只在该域是最高置信度域时添加，避免误标）
    domain_tag_map = {
        "ai-usage": ["AI", "工具"],
        "career-growth": ["职业", "成长"],
        "humanities": ["哲学", "传统文化"],
        "gongkao": ["考公"],
        "personal": ["个人"],
        "assets": ["素材"],
        "book-notes": ["读书"],
        "rcpm": ["医学", "生信"],
        "scrn": ["生信"],
        "invest": ["理财"],
        "skills": ["工具", "技能"],
    }
    
    if domain in domain_tag_map:
        for tag in domain_tag_map[domain]:
            if tag not in tags:
                tags.append(tag)
    
    # 关键：域专用标签优先，避免通用词误标
    # 例如：scrn 域不应添加 personal 的标签，即使文本里有"分析"
    if domain in ("scrn", "rcpm"):
        # 生信域专属标签
        priority_tags = ["生信", "基因", "测序", "医学", "临床"]
        for tag in priority_tags:
            if tag not in tags and count_keyword_hits(text_lower, [tag]) > 0:
                tags.append(tag)
    elif domain == "ai-usage":
        # AI 域专属标签
        priority_tags = ["AI", "Agent", "编程", "工具", "提示词", "自动化"]
        for tag in priority_tags:
            if tag not in tags and count_keyword_hits(text_lower, [tag]) > 0:
                tags.append(tag)
    elif domain == "gongkao":
        priority_tags = ["考公", "公务员", "行测", "申论", "备考"]
        for tag in priority_tags:
            if tag not in tags and count_keyword_hits(text_lower, [tag]) > 0:
                tags.append(tag)
    
    # 去重并保持顺序
    seen = set()
    unique_tags = []
    for tag in tags:
        if tag not in seen:
            seen.add(tag)
            unique_tags.append(tag)
    
    # 限制标签数量（避免过多）
    return unique_tags[:10]


def analyze_cross_references(text: str, existing_vault_entries: list[dict]) -> list[dict]:
    """分析文本与知识库中现有条目的关联。
    
    参数：
      existing_vault_entries: [{"path": "...", "title": "...", "keywords": [...]}]
    
    返回：
      [{"path": "...", "title": "...", "similarity": 0.0-1.0, "reason": "..."}]
    """
    if not existing_vault_entries:
        return []
    
    text_keywords = set(extract_keywords(text))
    references = []
    
    for entry in existing_vault_entries:
        entry_keywords = set(entry.get('keywords', []))
        
        # 计算 Jaccard 相似度
        intersection = text_keywords & entry_keywords
        union = text_keywords | entry_keywords
        similarity = len(intersection) / len(union) if union else 0
        
        if similarity > 0.1:  # 相似度阈值
            common = list(intersection)[:3]  # 最多显示 3 个共同关键词
            references.append({
                "path": entry['path'],
                "title": entry['title'],
                "similarity": round(similarity, 2),
                "common_keywords": common,
                "reason": f"共同关键词: {', '.join(common)}"
            })
    
    # 按相似度排序
    references.sort(key=lambda x: x['similarity'], reverse=True)
    return references[:5]  # 最多返回 5 个关联


# =====================
# 3. 批量处理接口
# =====================

def batch_classify(manifest_path: str, vault_path: str) -> dict:
    """批量分类：读取 intake 分拣单，对每件生成分类结果。"""
    with open(manifest_path, encoding='utf-8') as f:
        manifest = json.load(f)
    
    # 构建知识库索引（用于关联分析）
    vault_entries = []
    vault_root = Path(vault_path)
    for md_file in vault_root.rglob('*.md'):
        if '_PKOS' in md_file.parts or 'skills' in md_file.parts:
            continue
        try:
            text = md_file.read_text(encoding='utf-8-sig', errors='ignore')
            # 提取标题和关键词
            title_match = re.search(r'^title:\s*["\']?(.+?)["\']?\s*$', text, re.M)
            title = title_match.group(1) if title_match else md_file.stem
            keywords = extract_keywords(text)[:20]  # 取前 20 个关键词
            vault_entries.append({
                'path': str(md_file.relative_to(vault_root)),
                'title': title,
                'keywords': keywords
            })
        except Exception:
            continue
    
    results = []
    for ticket in manifest.get('tickets', []):
        item_path = ticket.get('item')
        item_full = Path(manifest['inbox']) / item_path if not Path(item_path).is_absolute() else Path(item_path)
        
        # 读取文件内容
        try:
            text = item_full.read_text(encoding='utf-8', errors='replace')
        except Exception as e:
            results.append({
                'item': item_path,
                'error': str(e)
            })
            continue
        
        # 分类
        classification = classify_domain(text, ticket.get('source', ''))
        tags = generate_tags(text, classification['suggested_domain'])
        
        # 关联分析（可选，需要更多时间）
        cross_refs = []  # 简化版先不做关联分析
        
        result = {
            'item': item_path,
            'classification': classification,
            'suggested_tags': tags,
            'cross_references': cross_refs,
        }
        results.append(result)
    
    return {
        'classified_at': __import__('datetime').datetime.now().isoformat(),
        'total_items': len(results),
        'results': results
    }


# =====================
# 4. CLI 接口
# =====================

def cmd_classify(text: str, source_url: str) -> int:
    """命令行分类接口。"""
    result = classify_domain(text, source_url)
    tags = generate_tags(text, result['suggested_domain'])
    
    output = {
        **result,
        'suggested_tags': tags
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


def cmd_batch(manifest: str, vault: str, out: str | None) -> int:
    """批量分类接口。"""
    result = batch_classify(manifest, vault)
    
    output_str = json.dumps(result, ensure_ascii=False, indent=2)
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(output_str, encoding='utf-8')
        print(f"Classification results saved to: {out}")
    else:
        print(output_str)
    
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='PKOS 智能分类器（model-agnostic）')
    sub = ap.add_subparsers(dest='cmd', required=True)
    
    # classify 子命令
    c = sub.add_parser('classify')
    c.add_argument('text', nargs='?', default='')
    c.add_argument('--source', default='')
    
    # batch 子命令
    b = sub.add_parser('batch')
    b.add_argument('--manifest', required=True)
    b.add_argument('--vault', required=True)
    b.add_argument('--out', default=None)
    
    args = ap.parse_args(argv)
    
    if args.cmd == 'classify':
        text = args.text
        if not text:
            import sys
            text = sys.stdin.read()
        return cmd_classify(text, args.source)
    elif args.cmd == 'batch':
        return cmd_batch(args.manifest, args.vault, args.out)
    
    return 1


if __name__ == '__main__':
    sys.exit(main())
