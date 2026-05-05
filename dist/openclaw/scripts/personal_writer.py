#!/usr/bin/env python3
"""
Lightweight personal writing workflow for WeWrite V1.

This module focuses on the "write like me" loop:
  - import published markdown articles into the exemplar library
  - prepare a writing brief from style/persona/history/exemplars/learned rules
  - learn from local markdown edits and persist learned_rules.yaml
  - run lightweight quality checks
  - append structured history records for dedupe and later review
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

import extract_exemplar

SKILL_DIR = Path(__file__).resolve().parent.parent
STYLE_PATH = SKILL_DIR / "style.yaml"
STYLE_EXAMPLE_PATH = SKILL_DIR / "style.example.yaml"
HISTORY_PATH = SKILL_DIR / "history.yaml"
LEARNED_RULES_PATH = SKILL_DIR / "learned_rules.yaml"
EXEMPLAR_INDEX_PATH = SKILL_DIR / "references" / "exemplars" / "index.yaml"
FRAMEWORKS_PATH = SKILL_DIR / "references" / "personal_frameworks.yaml"
ENHANCE_PATH = SKILL_DIR / "references" / "personal_enhance.yaml"
COMPETITOR_INDEX_PATH = SKILL_DIR / "references" / "competitors" / "index.yaml"

TOKEN_RE = re.compile(r"[A-Za-z]{2,16}|[\u4e00-\u9fff]{2,8}")
TITLE_FLAT_PATTERNS = ["什么是", "一文读懂", "指南", "深度解析", "全面了解"]
HOOK_MARKERS = ["为什么", "居然", "结果", "后来", "那天", "我才发现", "问题是", "但"]
SUMMARY_MARKERS = ["总之", "总而言之", "说到底", "归根结底", "最后想说", "总结一下"]
ORAL_MARKERS = ["其实", "真的", "说白了", "坦白说", "我觉得", "你会发现", "你可能"]
FIRST_PERSON_MARKERS = ["我", "我们", "自己"]
DETAIL_MARKERS = ["那天", "当时", "后来", "凌晨", "下午", "今天", "昨天", "数字", "截图"]


@dataclass
class Brief:
    topic: str
    keywords: list[str]
    persona: str
    framework: str
    framework_reason: str
    enhance_strategy: str
    enhance_reason: str
    recent_conflicts: list[str]
    selected_exemplars: list[dict[str, Any]]
    selected_competitors: list[dict[str, Any]]
    learned_rules: list[dict[str, Any]]
    seo: dict[str, Any]
    notes: list[str]


def load_yaml(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return default if data is None else data


def save_yaml(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        yaml.dump(data, fh, allow_unicode=True, default_flow_style=False, sort_keys=False)


def load_style() -> dict[str, Any]:
    style = load_yaml(STYLE_PATH, None)
    if style:
        return style
    return load_yaml(STYLE_EXAMPLE_PATH, {})


def load_persona(name: str | None = None) -> dict[str, Any]:
    style = load_style()
    persona_name = name or style.get("writing_persona") or "friend-voice"
    persona_path = SKILL_DIR / "personas" / f"{persona_name}.yaml"
    if not persona_path.exists():
        persona_path = SKILL_DIR / "personas" / "friend-voice.yaml"
    return load_yaml(persona_path, {})


def load_history() -> list[dict[str, Any]]:
    history = load_yaml(HISTORY_PATH, [])
    return history if isinstance(history, list) else []


def load_frameworks() -> dict[str, Any]:
    return load_yaml(FRAMEWORKS_PATH, {})


def load_enhance() -> dict[str, Any]:
    return load_yaml(ENHANCE_PATH, {})


def load_competitor_index() -> dict[str, Any]:
    return load_yaml(COMPETITOR_INDEX_PATH, {"accounts": []})


def load_learned_rules() -> dict[str, Any]:
    return load_yaml(
        LEARNED_RULES_PATH,
        {
            "version": 1,
            "updated_at": None,
            "rules": [],
        },
    )


def dump_payload(payload: Any, fmt: str) -> str:
    if fmt == "json":
        return json.dumps(payload, ensure_ascii=False, indent=2)
    return yaml.dump(payload, allow_unicode=True, default_flow_style=False, sort_keys=False)


def strip_frontmatter(text: str) -> str:
    if text.startswith("---\n"):
        parts = text.split("\n---\n", 1)
        if len(parts) == 2:
            return parts[1]
    return text


def read_article(path: Path) -> str:
    encodings = ["utf-8", "utf-8-sig", "gb18030", "gbk"]
    for encoding in encodings:
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore")


def extract_title(text: str) -> str:
    cleaned = strip_frontmatter(text)
    match = re.search(r"^#\s+(.+)$", cleaned, re.MULTILINE)
    return match.group(1).strip() if match else ""


def extract_tags(text: str) -> list[str]:
    frontmatter = {}
    if text.startswith("---\n"):
        parts = text.split("\n---\n", 1)
        if len(parts) == 2:
            frontmatter = yaml.safe_load(parts[0].strip("-\n")) or {}
    tags = frontmatter.get("tags", [])
    if isinstance(tags, str):
        return [tags]
    return [str(tag) for tag in tags]


def normalized_keywords(topic: str, supplied: list[str], style: dict[str, Any]) -> list[str]:
    keywords = [kw.strip() for kw in supplied if kw.strip()]
    if topic and topic not in keywords:
        keywords.insert(0, topic)
    for item in style.get("topics", [])[:3]:
        text = str(item).strip()
        if text and text not in keywords:
            keywords.append(text)
    seen = set()
    ordered = []
    for kw in keywords:
        if kw not in seen:
            ordered.append(kw)
            seen.add(kw)
    return ordered[:8]


def score_framework(topic: str, keywords: list[str], content_style: str, key: str, spec: dict[str, Any]) -> int:
    score = 0
    text = f"{topic} {' '.join(keywords)} {content_style}"
    for marker in spec.get("keywords", []):
        if marker and marker in text:
            score += 3
    for marker in spec.get("content_styles", []):
        if marker and marker in content_style:
            score += 2
    if key == "tutorial" and any(token in text for token in ["怎么", "教程", "步骤", "方法"]):
        score += 4
    if key == "list" and any(token in text for token in ["推荐", "清单", "合集", "工具"]):
        score += 4
    if key == "opinion" and any(token in text for token in ["为什么", "看法", "观点", "趋势", "值不值"]):
        score += 4
    if key == "story" and any(token in text for token in ["经历", "故事", "那次", "一次", "后来"]):
        score += 4
    if key == "recap" and any(token in text for token in ["复盘", "踩坑", "总结", "回顾"]):
        score += 4
    return score


def choose_framework(topic: str, keywords: list[str], style: dict[str, Any]) -> tuple[str, dict[str, Any], str]:
    frameworks = load_frameworks().get("frameworks", {})
    content_style = str(style.get("content_style", ""))
    ranked = []
    for key, spec in frameworks.items():
        ranked.append((score_framework(topic, keywords, content_style, key, spec), key, spec))
    ranked.sort(key=lambda item: item[0], reverse=True)
    _, key, spec = ranked[0]
    reason = spec.get("reason_template", "{topic} matches this structure").format(topic=topic)
    return key, spec, reason


def choose_enhance(framework_key: str) -> tuple[str, dict[str, Any], str]:
    strategies = load_enhance().get("strategies", {})
    mapping = {
        "list": "density_boost",
        "tutorial": "density_boost",
        "story": "detail_specificity",
        "recap": "detail_specificity",
        "opinion": "angle_sharpening",
    }
    key = mapping.get(framework_key, "density_boost")
    spec = strategies.get(key, {})
    reason = spec.get("reason", "")
    return key, spec, reason


def category_for_framework(framework_key: str) -> list[str]:
    mapping = {
        "list": ["list-practical", "general"],
        "tutorial": ["list-practical", "tech-opinion", "general"],
        "story": ["story-emotional", "general"],
        "recap": ["story-emotional", "tech-opinion", "general"],
        "opinion": ["tech-opinion", "hot-take", "general"],
    }
    return mapping.get(framework_key, ["general"])


def select_exemplars(framework_key: str, limit: int = 3) -> list[dict[str, Any]]:
    index = load_yaml(EXEMPLAR_INDEX_PATH, [])
    if not isinstance(index, list):
        return []
    categories = category_for_framework(framework_key)
    hits = [entry for entry in index if entry.get("category") in categories]
    hits.sort(key=lambda item: (categories.index(item.get("category")) if item.get("category") in categories else 99, item.get("humanness_score", 100)))
    return hits[:limit]


def score_competitor(framework_key: str, content_style: str, spec: dict[str, Any]) -> int:
    score = 0
    best_for = spec.get("best_for", {})
    frameworks = best_for.get("frameworks", [])
    styles = best_for.get("content_styles", [])
    if framework_key in frameworks:
        score += 5
    for style in styles:
        if style and style in content_style:
            score += 3
    return score


def select_competitors(style: dict[str, Any], framework_key: str, limit: int = 2) -> list[dict[str, Any]]:
    configured = style.get("reference_accounts", []) or []
    index = load_competitor_index().get("accounts", [])
    if not isinstance(configured, list) or not isinstance(index, list):
        return []

    content_style = str(style.get("content_style", ""))
    index_map = {item.get("id"): item for item in index if item.get("id")}
    selected = []
    for account_id in configured:
        meta = index_map.get(account_id)
        if not meta:
            continue
        for file_name in meta.get("files", []):
            spec_path = SKILL_DIR / "references" / "competitors" / file_name
            if not spec_path.exists():
                continue
            spec = load_yaml(spec_path, {})
            selected.append(
                {
                    "id": account_id,
                    "name": meta.get("name"),
                    "focus": meta.get("focus", []),
                    "style_tags": meta.get("style_tags", []),
                    "score": score_competitor(framework_key, content_style, spec),
                    "spec": spec,
                }
            )
    selected.sort(key=lambda item: item.get("score", 0), reverse=True)
    return selected[:limit]


def find_recent_conflicts(keywords: list[str], framework_key: str) -> list[str]:
    conflicts = []
    history = load_history()
    recent = history[-5:]
    for item in recent:
        old_keywords = item.get("topic_keywords", []) or []
        overlap = set(old_keywords) & set(keywords)
        if overlap:
            conflicts.append(f"recent topic overlap: {', '.join(sorted(overlap))}")
        if item.get("framework") == framework_key:
            conflicts.append(f"recent framework reused: {framework_key}")
    return conflicts[:5]


def generate_seo(topic: str, keywords: list[str], framework_key: str) -> dict[str, Any]:
    seed = keywords[0] if keywords else topic
    titles = [
        f"我最近重看{seed}，才发现真正难的不是开始",
        f"别急着下结论，{seed} 这件事我现在只信一半",
        f"{seed} 最容易被忽略的 3 个细节，我都踩过",
    ]
    if framework_key == "tutorial":
        titles = [
            f"{seed} 到底怎么上手？我按这个顺序走通了",
            f"刚开始碰 {seed} 时，我最希望有人直接告诉我的 5 步",
            f"{seed} 真正有用的不是技巧，是这套做法",
        ]
    elif framework_key == "list":
        titles = [
            f"{seed} 这几样我反复在用，顺手到不想换",
            f"如果你也在找 {seed}，先别乱试这 5 个",
            f"{seed} 不是越多越好，我最后只留下这几种",
        ]
    digest = f"围绕 {topic} 生成一篇更像作者本人、可直接发布到公众号的文章，重点覆盖 {'、'.join(keywords[:3])}。"
    tags = []
    for item in keywords:
        if item not in tags:
            tags.append(item)
    while len(tags) < 5:
        tags.append(f"{topic}观察")
    return {
        "titles": titles[:3],
        "digest": digest[:110],
        "tags": tags[:5],
        "keyword_coverage": {
            "must_cover": keywords[:5],
            "guidance": "intro should mention the first keyword within 200 Chinese characters",
        },
    }


def prepare_brief(topic: str, supplied_keywords: list[str]) -> Brief:
    style = load_style()
    persona_name = style.get("writing_persona") or "friend-voice"
    keywords = normalized_keywords(topic, supplied_keywords, style)
    framework_key, framework_spec, framework_reason = choose_framework(topic, keywords, style)
    enhance_key, _, enhance_reason = choose_enhance(framework_key)
    exemplars = select_exemplars(framework_key)
    competitors = select_competitors(style, framework_key)
    learned_rules = [rule for rule in load_learned_rules().get("rules", []) if rule.get("active", True)][:8]
    conflicts = find_recent_conflicts(keywords, framework_key)
    notes = []
    if not exemplars:
        notes.append("no exemplar matched; fallback to persona and style config")
    if competitors:
        names = ", ".join(item.get("name", "") for item in competitors)
        notes.append(f"competitor references: {names}")
    if conflicts:
        notes.append("review recent conflicts before drafting")
    notes.append(f"opening guidance: {framework_spec.get('opening')}")
    notes.append(f"outline: {' / '.join(framework_spec.get('outline', []))}")
    return Brief(
        topic=topic,
        keywords=keywords,
        persona=persona_name,
        framework=framework_key,
        framework_reason=framework_reason,
        enhance_strategy=enhance_key,
        enhance_reason=enhance_reason,
        recent_conflicts=conflicts,
        selected_exemplars=exemplars,
        selected_competitors=competitors,
        learned_rules=learned_rules,
        seo=generate_seo(topic, keywords, framework_key),
        notes=notes,
    )


def import_exemplars(target: Path) -> dict[str, Any]:
    if not target.exists():
        raise FileNotFoundError(f"{target} not found")
    files = [target] if target.is_file() else sorted(target.rglob("*.md"))
    imported = []
    skipped = []
    for path in files:
        text = read_article(path)
        title = extract_title(text) or path.stem
        exemplar = extract_exemplar.extract_exemplar(text, source=title)
        segments = exemplar.get("segments", {})
        useful_segments = sum(1 for value in segments.values() if value)
        if useful_segments == 0:
            skipped.append({"file": str(path), "reason": "no useful segments"})
            continue
        saved = extract_exemplar.save_exemplar(exemplar)
        imported.append(
            {
                "file": str(path),
                "saved_to": str(saved),
                "category": exemplar.get("category"),
                "humanness_score": exemplar.get("humanness_score"),
                "segments": useful_segments,
            }
        )
    return {"imported": imported, "skipped": skipped}


def split_paragraphs(text: str) -> list[str]:
    cleaned = strip_frontmatter(text)
    paragraphs = [paragraph.strip() for paragraph in re.split(r"\n\s*\n", cleaned) if paragraph.strip()]
    return [paragraph for paragraph in paragraphs if not paragraph.startswith("#")]


def token_counts(text: str) -> Counter[str]:
    tokens = [token for token in TOKEN_RE.findall(text) if len(token) >= 2]
    return Counter(tokens)


def count_hits(text: str, terms: list[str]) -> int:
    return sum(text.count(term) for term in terms)


def detect_opening_type(text: str) -> str:
    first = "\n".join(split_paragraphs(text)[:2])
    if any(marker in first for marker in ["那天", "后来", "凌晨", "当时"]):
        return "scene"
    if "我" in first:
        return "personal"
    if any(marker in first for marker in ["为什么", "问题是", "但"]):
        return "conflict"
    return "plain"


def detect_closing_type(text: str) -> str:
    paragraphs = split_paragraphs(text)
    closing = paragraphs[-1] if paragraphs else ""
    if any(marker in closing for marker in SUMMARY_MARKERS):
        return "summary"
    if closing.endswith("。") and "我" in closing:
        return "personal_note"
    if "问题" in closing or "你" in closing:
        return "open_question"
    return "soft_close"


def build_rule(rule_id: str, rule_type: str, instruction: str, evidence: Any) -> dict[str, Any]:
    return {
        "id": rule_id,
        "type": rule_type,
        "instruction": instruction,
        "active": True,
        "evidence_count": 1,
        "last_seen": datetime.now().strftime("%Y-%m-%d"),
        "examples": [evidence] if evidence else [],
    }


def merge_rule(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    existing["instruction"] = incoming["instruction"]
    existing["active"] = True
    existing["evidence_count"] = int(existing.get("evidence_count", 0)) + 1
    existing["last_seen"] = incoming["last_seen"]
    examples = list(existing.get("examples", []))
    for example in incoming.get("examples", []):
        if example not in examples:
            examples.append(example)
    existing["examples"] = examples[:5]
    return existing


def learn_from_diff(draft_path: Path, final_path: Path) -> dict[str, Any]:
    draft_text = read_article(draft_path)
    final_text = read_article(final_path)
    draft_plain = strip_frontmatter(draft_text)
    final_plain = strip_frontmatter(final_text)

    learned_rules = load_learned_rules()
    rules_by_id = {rule.get("id"): rule for rule in learned_rules.get("rules", [])}
    new_rules = []

    draft_counts = token_counts(draft_plain)
    final_counts = token_counts(final_plain)

    removed_summaries = count_hits(draft_plain, SUMMARY_MARKERS) - count_hits(final_plain, SUMMARY_MARKERS)
    if removed_summaries > 0:
        new_rules.append(
            build_rule(
                "trim_summary_tone",
                "tone",
                "avoid long summary-style endings; close with a personal note or an open thread instead",
                {"draft": draft_path.name, "final": final_path.name},
            )
        )

    draft_oral = count_hits(draft_plain, ORAL_MARKERS)
    final_oral = count_hits(final_plain, ORAL_MARKERS)
    if final_oral > draft_oral:
        new_rules.append(
            build_rule(
                "increase_oral_markers",
                "expression",
                "lean slightly more conversational by using natural oral markers only where they sound human",
                {"before": draft_oral, "after": final_oral},
            )
        )

    draft_first = count_hits(draft_plain, FIRST_PERSON_MARKERS)
    final_first = count_hits(final_plain, FIRST_PERSON_MARKERS)
    if abs(final_first - draft_first) >= 3:
        direction = "increase" if final_first > draft_first else "reduce"
        new_rules.append(
            build_rule(
                "first_person_density",
                "tone",
                f"{direction} first-person presence so the narration stays closer to the author's natural voice",
                {"before": draft_first, "after": final_first},
            )
        )

    draft_paragraph_lengths = [len(item) for item in split_paragraphs(draft_plain)]
    final_paragraph_lengths = [len(item) for item in split_paragraphs(final_plain)]
    if draft_paragraph_lengths and final_paragraph_lengths:
        draft_avg = sum(draft_paragraph_lengths) / len(draft_paragraph_lengths)
        final_avg = sum(final_paragraph_lengths) / len(final_paragraph_lengths)
        if abs(final_avg - draft_avg) >= 20:
            if final_avg < draft_avg:
                instruction = "keep paragraphs shorter and break long explanations earlier"
                rule_id = "shorter_paragraphs"
            else:
                instruction = "allow slightly fuller paragraphs when the point needs one more beat"
                rule_id = "fuller_paragraphs"
            new_rules.append(
                build_rule(rule_id, "structure", instruction, {"before": round(draft_avg, 1), "after": round(final_avg, 1)})
            )

    draft_opening = detect_opening_type(draft_plain)
    final_opening = detect_opening_type(final_plain)
    if draft_opening != final_opening:
        new_rules.append(
            build_rule(
                "opening_preference",
                "structure",
                f"prefer a {final_opening} opening instead of a {draft_opening} opening when drafting",
                {"before": draft_opening, "after": final_opening},
            )
        )

    draft_closing = detect_closing_type(draft_plain)
    final_closing = detect_closing_type(final_plain)
    if draft_closing != final_closing:
        new_rules.append(
            build_rule(
                "closing_preference",
                "structure",
                f"prefer a {final_closing} ending instead of a {draft_closing} ending",
                {"before": draft_closing, "after": final_closing},
            )
        )

    removed_tokens = [token for token, count in draft_counts.items() if count >= 2 and final_counts[token] < count]
    preferred_tokens = [token for token, count in final_counts.items() if count >= 2 and draft_counts[token] < count]
    if removed_tokens:
        top_removed = sorted(removed_tokens, key=lambda token: draft_counts[token] - final_counts[token], reverse=True)[:5]
        new_rules.append(
            build_rule(
                "avoid_terms",
                "word_choice",
                "avoid overused draft terms unless they are necessary for meaning",
                {"terms": top_removed},
            )
        )
    if preferred_tokens:
        top_added = sorted(preferred_tokens, key=lambda token: final_counts[token] - draft_counts[token], reverse=True)[:5]
        new_rules.append(
            build_rule(
                "preferred_terms",
                "word_choice",
                "prefer the author's recurring word choices when a similar meaning is needed",
                {"terms": top_added},
            )
        )

    for rule in new_rules:
        rule_id = rule["id"]
        if rule_id in rules_by_id:
            rules_by_id[rule_id] = merge_rule(rules_by_id[rule_id], rule)
        else:
            rules_by_id[rule_id] = rule

    merged = sorted(rules_by_id.values(), key=lambda item: (-int(item.get("evidence_count", 0)), item.get("id", "")))
    learned_rules["version"] = 1
    learned_rules["updated_at"] = datetime.now().isoformat()
    learned_rules["rules"] = merged
    save_yaml(LEARNED_RULES_PATH, learned_rules)

    return {
        "draft": str(draft_path),
        "final": str(final_path),
        "new_rules": new_rules,
        "total_rules": len(merged),
        "output": str(LEARNED_RULES_PATH),
    }


def validate_article(article_path: Path) -> dict[str, Any]:
    style = load_style()
    text = read_article(article_path)
    body = strip_frontmatter(text)
    title = extract_title(text)
    paragraphs = split_paragraphs(body)
    issues = []

    blacklist = style.get("blacklist", [])
    if isinstance(blacklist, dict):
        blacklist_words = blacklist.get("words", [])
    else:
        blacklist_words = blacklist
    hits = [word for word in blacklist_words if word and word in body]
    if hits:
        issues.append({"id": "blacklist", "severity": "high", "message": f"blacklist words found: {', '.join(hits[:8])}"})

    if any(pattern in title for pattern in TITLE_FLAT_PATTERNS):
        issues.append({"id": "flat_title", "severity": "high", "message": "title reads like a guide or explainer; add tension or curiosity"})

    opening_text = " ".join(paragraphs[:2])
    if not any(marker in opening_text for marker in HOOK_MARKERS):
        issues.append({"id": "weak_opening", "severity": "medium", "message": "opening lacks conflict, surprise, or a personal scene"})

    detail_hits = count_hits(body, DETAIL_MARKERS) + len(re.findall(r"\d+", body))
    if detail_hits < 3:
        issues.append({"id": "thin_details", "severity": "medium", "message": "article needs more concrete details, scenes, or numbers"})

    if len(paragraphs) >= 3:
        paragraph_lengths = [len(item) for item in paragraphs]
        if max(paragraph_lengths) - min(paragraph_lengths) < 30:
            issues.append({"id": "flat_rhythm", "severity": "low", "message": "paragraph rhythm is too even; vary sentence and paragraph length"})

    keywords = extract_tags(text)
    coverage = {}
    first_200 = body[:200]
    for keyword in keywords[:5]:
        coverage[keyword] = keyword in first_200 or keyword in body
    if keywords and not any(coverage.values()):
        issues.append({"id": "keyword_coverage", "severity": "low", "message": "frontmatter tags are not reflected naturally in the article body"})

    passed = len([issue for issue in issues if issue["severity"] == "high"]) == 0
    return {
        "article": str(article_path),
        "title": title,
        "passed": passed,
        "issues": issues,
        "keyword_coverage": coverage,
        "opening_type": detect_opening_type(body),
        "closing_type": detect_closing_type(body),
    }


def append_history(article_path: Path, topic: str, plan_path: Path | None = None) -> dict[str, Any]:
    article_text = read_article(article_path)
    title = extract_title(article_text) or article_path.stem
    tags = extract_tags(article_text)
    plan = load_yaml(plan_path, {}) if plan_path else {}
    history = load_history()
    persona_name = plan.get("persona") or load_style().get("writing_persona") or "friend-voice"
    framework = plan.get("framework") or "unknown"
    enhance = plan.get("enhance_strategy") or "unknown"
    exemplars = [item.get("file") for item in plan.get("selected_exemplars", [])]
    learned_rule_ids = [item.get("id") for item in plan.get("learned_rules", [])]
    record = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "title": title,
        "topic_source": "user_request",
        "topic_keywords": tags or [topic],
        "output_file": str(article_path),
        "framework": framework,
        "enhance_strategy": enhance,
        "word_count": len(strip_frontmatter(article_text).replace("\n", "")),
        "media_id": None,
        "writing_persona": persona_name,
        "selected_exemplars": exemplars,
        "learned_rules_hit": learned_rule_ids,
        "opening_type": detect_opening_type(article_text),
        "closing_type": detect_closing_type(article_text),
        "stats": {
            "read": None,
            "like": None,
            "share": None,
            "wow": None,
            "note": None,
        },
    }
    history.append(record)
    save_yaml(HISTORY_PATH, history)
    return record


def main() -> None:
    parser = argparse.ArgumentParser(description="Lightweight personal writing workflow")
    sub = parser.add_subparsers(dest="command", required=True)

    p_import = sub.add_parser("import-exemplars", help="Import local markdown articles into the exemplar library")
    p_import.add_argument("path", help="Markdown file or directory")
    p_import.add_argument("--json", action="store_true", help="JSON output")

    p_plan = sub.add_parser("plan", help="Prepare a writing brief from style/persona/history")
    p_plan.add_argument("topic", help="Writing topic")
    p_plan.add_argument("--keyword", action="append", default=[], help="Additional keyword")
    p_plan.add_argument("--output", help="Write plan to a file")
    p_plan.add_argument("--format", choices=["yaml", "json"], default="yaml", help="Output format")

    p_learn = sub.add_parser("learn", help="Learn author preferences from draft/final markdown diff")
    p_learn.add_argument("--draft", required=True, help="Draft markdown path")
    p_learn.add_argument("--final", required=True, help="Final markdown path")
    p_learn.add_argument("--format", choices=["yaml", "json"], default="yaml", help="Output format")

    p_qc = sub.add_parser("qc", help="Run lightweight article quality checks")
    p_qc.add_argument("article", help="Markdown article path")
    p_qc.add_argument("--format", choices=["yaml", "json"], default="yaml", help="Output format")

    p_log = sub.add_parser("log", help="Append a history record for an article")
    p_log.add_argument("article", help="Markdown article path")
    p_log.add_argument("--topic", required=True, help="Original topic")
    p_log.add_argument("--plan", help="Plan file produced by writer plan")
    p_log.add_argument("--format", choices=["yaml", "json"], default="yaml", help="Output format")

    args = parser.parse_args()

    if args.command == "import-exemplars":
        result = import_exemplars(Path(args.path))
        payload = json.dumps(result, ensure_ascii=False, indent=2) if args.json else yaml.dump(result, allow_unicode=True, default_flow_style=False, sort_keys=False)
        print(payload)
        return

    if args.command == "plan":
        brief = prepare_brief(args.topic, args.keyword)
        payload = {
            "topic": brief.topic,
            "keywords": brief.keywords,
            "persona": brief.persona,
            "framework": brief.framework,
            "framework_reason": brief.framework_reason,
            "enhance_strategy": brief.enhance_strategy,
            "enhance_reason": brief.enhance_reason,
            "recent_conflicts": brief.recent_conflicts,
            "selected_exemplars": brief.selected_exemplars,
            "selected_competitors": [
                {
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "style_tags": item.get("style_tags", []),
                    "borrow_rules": item.get("spec", {}).get("borrow_rules", {}),
                    "title_patterns": item.get("spec", {}).get("signals", {}).get("title_patterns", []),
                    "opening_patterns": item.get("spec", {}).get("signals", {}).get("opening_patterns", []),
                    "structure_patterns": item.get("spec", {}).get("signals", {}).get("structure_patterns", []),
                }
                for item in brief.selected_competitors
            ],
            "learned_rules": brief.learned_rules,
            "seo": brief.seo,
            "notes": brief.notes,
        }
        rendered = dump_payload(payload, args.format)
        if args.output:
            Path(args.output).write_text(rendered, encoding="utf-8")
        print(rendered)
        return

    if args.command == "learn":
        payload = learn_from_diff(Path(args.draft), Path(args.final))
        print(dump_payload(payload, args.format))
        return

    if args.command == "qc":
        payload = validate_article(Path(args.article))
        print(dump_payload(payload, args.format))
        return

    if args.command == "log":
        payload = append_history(Path(args.article), args.topic, Path(args.plan) if args.plan else None)
        print(dump_payload(payload, args.format))
        return


if __name__ == "__main__":
    main()
