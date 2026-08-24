"""LLM Result Synthesizer — takes test results + charts → statistician answer."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from litellm import acompletion

from app.ai.models import SynthesizedAnswer, TestResult
from app.ai.parser import _extract_json

PROMPT_DIR = Path(__file__).resolve().parent / "prompts"
SYNTHESIZER_PROMPT = (PROMPT_DIR / "synthesizer.md").read_text(encoding="utf-8") if (PROMPT_DIR / "synthesizer.md").exists() else ""


def _get_api_key() -> Optional[str]:
    return os.getenv("DEEPSEEK_API_KEY") or None


def _get_llm_config() -> Dict[str, Any]:
    return {
        "model": os.getenv("DEEPSEEK_MODEL", "deepseek/deepseek-v4-pro"),
        "temperature": 0.1,
        "max_tokens": 4096,
    }


async def synthesize_results(
    results: List[TestResult],
    user_query: str,
) -> SynthesizedAnswer:
    """Synthesize all test results into a statistician answer."""
    if not results:
        return SynthesizedAnswer(summary="No tests were executed. Please confirm an analysis plan first.")

    results_data = _format_results(results)
    user_prompt = (
        f"# Results Data\n```json\n{json.dumps(results_data, indent=2, default=str)}\n```\n\n"
        f"# User's Original Question\n```\n{user_query}\n```"
    )

    cfg = _get_llm_config()
    messages = [
        {"role": "system", "content": SYNTHESIZER_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    response = await acompletion(
        model=cfg["model"],
        messages=messages,
        temperature=cfg["temperature"],
        max_tokens=cfg["max_tokens"],
        api_key=_get_api_key(),
    )

    raw = response.choices[0].message.content
    json_str = _extract_json(raw)
    data = json.loads(json_str)

    return SynthesizedAnswer(
        summary=data.get("summary", ""),
        detailed_results=data.get("detailed_results", []),
        limitations=data.get("limitations", ""),
        conclusion=data.get("conclusion", ""),
    )


def _format_results(results: List[TestResult]) -> Dict[str, Any]:
    return {
        "total_tests": len(results),
        "tests": [
            {
                "test_name": r.test_name,
                "status": r.status,
                "used_fallback": r.used_fallback,
                "fallback_reason": r.fallback_reason if r.used_fallback else None,
                "error": r.error,
                "response": r.response,
                "charts": [{"type": c["type"], "title": c["title"]} for c in r.charts],
            }
            for r in results
        ],
    }
