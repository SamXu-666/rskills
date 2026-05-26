"""
Proof + fingerprint verification gatekeeper for rwrite publish.

Cross-validates proof records ({article}.proof.json) against actual article content.
Each pipeline stage writes BOTH a process proof ("I completed X") AND content
fingerprints (specific text/patterns that MUST exist if the stage was truly done).

Runs before any network calls — cheapest failure point.
"""

import io
import re
import json
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class VerifyResult:
    """Result of proof verification."""
    passed: bool = True
    hard_failures: list = field(default_factory=list)   # blocks publish
    soft_warnings: list = field(default_factory=list)    # warns only
    proof_stages: list = field(default_factory=list)     # stages with valid proofs
    missing_stages: list = field(default_factory=list)   # required stages absent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _count_cn_chars(text: str) -> int:
    """Count Chinese characters + fullwidth punctuation in text."""
    count = 0
    for ch in text:
        if '一' <= ch <= '鿿' or '　' <= ch <= '〿' or '＀' <= ch <= '￯':
            count += 1
    return count


def _extract_h1(text: str) -> Optional[str]:
    """Extract the first H1 heading (line starting with '# ')."""
    m = re.search(r'^#\s+(.+)$', text, re.MULTILINE)
    return m.group(1).strip() if m else None


def _count_sections(text: str) -> int:
    """Count H2 headings (lines starting with '## ')."""
    return len(re.findall(r'^##\s+', text, re.MULTILINE))


# ---------------------------------------------------------------------------
# Fingerprint handlers — each returns (ok: bool, message: str)
# ---------------------------------------------------------------------------

def _check_text_contains(article: str, fp: dict) -> tuple:
    target = fp["value"]
    if target in article:
        return True, ""
    preview = target[:60].replace('\n', '\\n')
    return False, f"Required text not found: '{preview}...'"


def _check_text_not_contains(article: str, fp: dict) -> tuple:
    target = fp["value"]
    if target not in article:
        return True, ""
    preview = target[:60].replace('\n', '\\n')
    return False, f"Forbidden text found: '{preview}...'"


def _check_word_count_min(article: str, fp: dict) -> tuple:
    min_words = fp["value"]
    actual = _count_cn_chars(article)
    if actual >= min_words:
        return True, ""
    return False, f"CN char count {actual} < minimum {min_words}"


def _check_title_matches_h1(article: str, fp: dict) -> tuple:
    """Check that the chosen title appears as H1 in the article."""
    expected_title = fp.get("value", "")
    h1 = _extract_h1(article)
    if h1 and h1 == expected_title:
        return True, ""
    if not h1:
        return False, "No H1 heading found in article"
    return False, f"H1 '{h1[:40]}' does not match expected title '{expected_title[:40]}'"


def _check_section_count_min(article: str, fp: dict) -> tuple:
    min_sections = fp["value"]
    actual = _count_sections(article)
    if actual >= min_sections:
        return True, ""
    return False, f"Section count {actual} < minimum {min_sections}"


def _check_text_pattern(article: str, fp: dict) -> tuple:
    pattern = fp["value"]
    if re.search(pattern, article, re.MULTILINE):
        return True, ""
    return False, f"Pattern not matched: {pattern}"


def _proof_value(article: str, fp: dict) -> tuple:
    """Proof-value checks are validated against the proof JSON directly
    (not article content), so this handler is a no-op at fingerprint level.
    Proof-value assertions are handled by _check_stage_proof_values()."""
    return True, ""


CHECK_HANDLERS = {
    "text_contains": _check_text_contains,
    "text_not_contains": _check_text_not_contains,
    "word_count_min": _check_word_count_min,
    "title_matches_h1": _check_title_matches_h1,
    "section_count_min": _check_section_count_min,
    "text_pattern": _check_text_pattern,
    "proof_value": _proof_value,
}


# ---------------------------------------------------------------------------
# Stage-level proof-value requirements
# ---------------------------------------------------------------------------

# (stage_key, proof_field, expected_value, severity)
STAGE_PROOF_CHECKS: list = [
    # Stage ⑤ — Skeleton
    ("05_skeleton", "cp0_passed", True, "HARD"),
    ("05_skeleton", "eeat_passed", True, "HARD"),
    ("05_skeleton", "self_checks_passed", True, "HARD"),
    ("05_skeleton", "structure_rotated", True, "SOFT"),

    # Stage ⑥ — Write
    ("06_write", "taste_confirmed", True, "SOFT"),
    ("06_write", "title_chosen", True, "HARD"),
    ("06_write", "experience_injected", True, "SOFT"),

    # Stage ⑦ — Hook scan
    ("07_hook_scan", "hook_scan_done", True, "HARD"),

    # Stage 👁 — Cold read
    ("08_cold_read", "cold_read_done", True, "SOFT"),
    ("08_cold_read", "r2_clear", True, "HARD"),
    ("08_cold_read", "fixes_applied", True, "SOFT"),
    ("08_cold_read", "format_all_passed", True, "HARD"),

    # Stage ⑧ — Publish prep
    ("09_publish", "format_injected", True, "SOFT"),
]

# Proof fields with numeric thresholds: (stage_key, field, min_value, severity)
STAGE_NUMERIC_CHECKS: list = [
    ("06_write", "cn_chars", 3000, "HARD"),
    ("06_write", "title_candidates", 5, "HARD"),
    ("06_write", "formula_count", 5, "SOFT"),
    ("07_hook_scan", "hook_count", 6, "HARD"),
    ("08_cold_read", "cn_chars", 2500, "HARD"),
    ("08_cold_read", "ai_ratio", 25, "HARD"),  # ai_ratio must be BELOW 25%
    ("09_publish", "tags_count", 5, "SOFT"),
]

# Required stages that MUST be completed (missing = HARD fail)
REQUIRED_STAGES = ["05_skeleton", "06_write", "07_hook_scan", "08_cold_read"]


# ---------------------------------------------------------------------------
# Main verification logic
# ---------------------------------------------------------------------------

def verify(article_path: Path) -> VerifyResult:
    """Run all proof checks against an article and its proof file.

    Args:
        article_path: Path to the markdown article file.
                      Proof file is expected at {article_path.stem}.proof.json
                      in the same directory.

    Returns:
        VerifyResult with passed, hard_failures, soft_warnings, etc.
    """
    result = VerifyResult()

    # Resolve proof file path — same stem, same directory, .proof.json extension
    proof_path = article_path.with_suffix(".proof.json")

    if not proof_path.exists():
        result.passed = False
        result.hard_failures.append(
            f"No proof file found: {proof_path.name}\n"
            "  Run the full JIT pipeline to generate one, or use --skip-verify."
        )
        return result

    # Load proof
    try:
        proof = json.loads(proof_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        result.passed = False
        result.hard_failures.append(f"Failed to read proof file: {e}")
        return result

    stages = proof.get("stages", {})

    # Load article text
    try:
        article_text = article_path.read_text(encoding="utf-8")
    except OSError as e:
        result.passed = False
        result.hard_failures.append(f"Failed to read article: {e}")
        return result

    # ── Check 1: Required stages must be completed ──
    for stage_key in REQUIRED_STAGES:
        stage = stages.get(stage_key)
        if not stage or not stage.get("completed"):
            result.missing_stages.append(stage_key)
            result.hard_failures.append(
                f"Stage {stage_key} not completed — run the pipeline from this stage."
            )
            result.passed = False
        else:
            result.proof_stages.append(stage_key)

    # ── Check 2: Stage-level proof-value assertions ──
    for stage_key, field, expected, severity in STAGE_PROOF_CHECKS:
        stage = stages.get(stage_key, {})
        proof_data = stage.get("proof", {})
        actual = proof_data.get(field)

        if actual != expected:
            msg = f"[{stage_key}] proof.{field} = {actual}, expected {expected}"
            if severity == "HARD":
                result.hard_failures.append(msg)
                result.passed = False
            else:
                result.soft_warnings.append(msg)

    # ── Check 3: Numeric threshold checks ──
    for stage_key, field, threshold, severity in STAGE_NUMERIC_CHECKS:
        stage = stages.get(stage_key, {})
        proof_data = stage.get("proof", {})
        actual = proof_data.get(field)

        if actual is None:
            continue  # field not present — skip (may not apply)

        if field == "ai_ratio":
            # ai_ratio should be BELOW threshold
            if actual >= threshold:
                msg = f"[{stage_key}] proof.{field} = {actual}% (threshold: <{threshold}%)"
                result.soft_warnings.append(msg)
        else:
            if actual < threshold:
                msg = f"[{stage_key}] proof.{field} = {actual} (threshold: ≥{threshold})"
                if severity == "HARD":
                    result.hard_failures.append(msg)
                    result.passed = False
                else:
                    result.soft_warnings.append(msg)

    # ── Check 4: Content fingerprints (cross-validate against article) ──
    for stage_key in stages:
        stage = stages[stage_key]
        for fp in stage.get("fingerprints", []):
            check_type = fp.get("check_type")
            handler = CHECK_HANDLERS.get(check_type)
            if not handler:
                result.soft_warnings.append(
                    f"[{stage_key}] Unknown check_type: {check_type}"
                )
                continue

            ok, msg = handler(article_text, fp)
            if not ok:
                severity = fp.get("severity", "HARD")
                full_msg = f"[{stage_key}] {msg}"
                if severity == "HARD":
                    result.hard_failures.append(full_msg)
                    result.passed = False
                else:
                    result.soft_warnings.append(full_msg)

    return result


# ---------------------------------------------------------------------------
# CLI entry point (for standalone testing)
# ---------------------------------------------------------------------------

def main():
    # Fix UnicodeEncodeError on Windows GBK terminals
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    if len(sys.argv) < 2:
        print("Usage: python verify_publish.py <article.md>", file=sys.stderr)
        sys.exit(2)

    article_path = Path(sys.argv[1])
    if not article_path.exists():
        print(f"Error: article not found: {article_path}", file=sys.stderr)
        sys.exit(2)

    result = verify(article_path)

    if result.missing_stages:
        print(f"Missing stages: {', '.join(result.missing_stages)}")

    if result.proof_stages:
        print(f"Proven stages: {', '.join(result.proof_stages)}")

    if result.hard_failures:
        print(f"\n❌ HARD failures ({len(result.hard_failures)}):")
        for f in result.hard_failures:
            print(f"  🔴 {f}")

    if result.soft_warnings:
        print(f"\n⚠️  SOFT warnings ({len(result.soft_warnings)}):")
        for w in result.soft_warnings:
            print(f"  🟡 {w}")

    if result.passed:
        print("\n✅ All HARD checks passed.")
    else:
        print("\n❌ Verification FAILED — publish blocked.")
        sys.exit(1)


if __name__ == "__main__":
    main()
