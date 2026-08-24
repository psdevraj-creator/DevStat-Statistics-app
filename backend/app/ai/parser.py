"""LLM Goal Parser — takes plain language + data dictionary → structured AnalysisPlan."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from litellm import acompletion

# Load .env from backend root or devstat-ai root
_env_path = Path(__file__).resolve().parent.parent.parent.parent / '.env'
if not _env_path.exists():
    _env_path = Path(__file__).resolve().parent.parent.parent.parent.parent / 'devstat-ai' / '.env'
if _env_path.exists():
    load_dotenv(dotenv_path=_env_path)

from app.ai.models import AnalysisPlan, ChartProposal, DataTransform, TestProposal
from app.ai.scanner import format_data_dictionary

PROMPT_DIR = Path(__file__).resolve().parent / "prompts"
GOAL_PARSER_PROMPT = (PROMPT_DIR / "goal_parser.md").read_text(encoding="utf-8") if (PROMPT_DIR / "goal_parser.md").exists() else ""


def _get_api_key() -> Optional[str]:
    return os.getenv("DEEPSEEK_API_KEY") or None


def _get_llm_config() -> Dict[str, Any]:
    return {
        "model": os.getenv("DEEPSEEK_MODEL", "deepseek/deepseek-v4-pro"),
        "temperature": 0.1,
        "max_tokens": 4096,
    }


async def call_llm(
    system_prompt: str,
    user_prompt: str,
    api_key: Optional[str] = None,
) -> str:
    cfg = _get_llm_config()
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    response = await acompletion(
        model=cfg["model"],
        messages=messages,
        temperature=cfg["temperature"],
        max_tokens=cfg["max_tokens"],
        api_key=api_key or _get_api_key(),
    )
    return response.choices[0].message.content


def _extract_json(text: str) -> str:
    m = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        return m.group(0).strip()
    return text.strip()


async def parse_goal(
    user_query: str,
    max_tests: int = 5,
) -> AnalysisPlan:
    """Parse user query into an AnalysisPlan using LLM."""
    dict_formatted = format_data_dictionary()

    system_prompt = GOAL_PARSER_PROMPT.replace("{max_tests}", str(max_tests))
    user_prompt = (
        f"# Dataset Description\n```\n{dict_formatted}\n```\n\n"
        f"# User's Question\n```\n{user_query}\n```"
    )

    raw = await call_llm(system_prompt, user_prompt)
    json_str = _extract_json(raw)
    data = json.loads(json_str)

    tests = []
    for t in data.get("tests", []):
        charts = [ChartProposal(**c) for c in t.get("charts", [])]
        tests.append(TestProposal(
            id=t.get("id", f"test_{len(tests) + 1}"),
            test=t["test"],
            test_name=t.get("test_name", t["test"]),
            rationale=t.get("rationale", ""),
            endpoint=t.get("endpoint", ""),
            payload=t.get("payload", {}),
            charts=charts,
            assumptions=t.get("assumptions", []),
            fallback_test=t.get("fallback_test"),
        ))

    transforms = [DataTransform(**dt) for dt in data.get("data_transforms", [])]

    return AnalysisPlan(
        plan_name=data.get("plan_name", "Unnamed Plan"),
        tests=tests,
        notes=data.get("notes", ""),
        data_transforms=transforms,
    )
