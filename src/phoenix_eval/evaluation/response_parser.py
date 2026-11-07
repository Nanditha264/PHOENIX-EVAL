"""Robust parsing engine for AI model evaluation responses.

Extracts structured JSON from raw text strings, Markdown code blocks,
and handles malformed, truncated, or schema-violating outputs safely
without terminating benchmark execution or masking underlying defects.
"""

import json
import re
from dataclasses import dataclass
from typing import Any, Optional

from pydantic import ValidationError

from phoenix_eval.schemas.response_contract import ModelResponseContract


@dataclass(frozen=True)
class ParsedResponse:
    """Encapsulates the parsing and structural validation outcome of a model response."""

    raw_text: str
    cleaned_json_text: str
    json_parsed: bool
    parsed_dict: Optional[dict[str, Any]]
    model_contract: Optional[ModelResponseContract]
    is_valid_contract: bool
    is_malformed: bool
    errors: list[str]


def extract_json_payload(raw_text: str) -> str:
    """Extract clean JSON text, stripping Markdown code fences and peripheral text."""
    text = raw_text.strip()
    if not text:
        return ""

    # 1. Match Markdown code fences: ```json ... ``` or ``` ... ```
    fence_pattern = re.compile(r"```(?:json)?\s*\n?([\s\S]*?)\n?```", re.IGNORECASE)
    matches = fence_pattern.findall(text)
    if matches:
        # Prefer the largest or first JSON block
        candidate = matches[0].strip()
        if candidate.startswith("{") and candidate.endswith("}"):
            return str(candidate)

    # 2. Match outer curly braces if embedded in prose
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        return text[first_brace : last_brace + 1].strip()

    return text


def parse_model_response(raw_response: str) -> ParsedResponse:
    """Safely parse and validate a model's response string against ModelResponseContract.

    Never raises unhandled parsing exceptions; all syntax and schema errors
    are captured as machine-readable error records.
    """
    cleaned_text = extract_json_payload(raw_response)
    errors: list[str] = []

    if not cleaned_text:
        return ParsedResponse(
            raw_text=raw_response,
            cleaned_json_text="",
            json_parsed=False,
            parsed_dict=None,
            model_contract=None,
            is_valid_contract=False,
            is_malformed=True,
            errors=["Response is empty or contains no JSON payload."],
        )

    # Attempt JSON decoding
    parsed_dict: Optional[dict[str, Any]] = None
    try:
        parsed_dict = json.loads(cleaned_text)
    except json.JSONDecodeError as decode_err:
        return ParsedResponse(
            raw_text=raw_response,
            cleaned_json_text=cleaned_text,
            json_parsed=False,
            parsed_dict=None,
            model_contract=None,
            is_valid_contract=False,
            is_malformed=True,
            errors=[
                f"JSON syntax error at line {decode_err.lineno}, col {decode_err.colno}: {decode_err.msg}"
            ],
        )

    if not isinstance(parsed_dict, dict):
        return ParsedResponse(
            raw_text=raw_response,
            cleaned_json_text=cleaned_text,
            json_parsed=True,
            parsed_dict=None,
            model_contract=None,
            is_valid_contract=False,
            is_malformed=True,
            errors=[f"Expected JSON object (dict), got {type(parsed_dict).__name__}."],
        )

    # Attempt Pydantic contract validation
    try:
        contract = ModelResponseContract.model_validate(parsed_dict)
        return ParsedResponse(
            raw_text=raw_response,
            cleaned_json_text=cleaned_text,
            json_parsed=True,
            parsed_dict=parsed_dict,
            model_contract=contract,
            is_valid_contract=True,
            is_malformed=False,
            errors=[],
        )
    except ValidationError as val_err:
        for issue in val_err.errors():
            loc = ".".join(str(p) for p in issue["loc"])
            msg = issue["msg"]
            errors.append(f"Schema violation at '{loc}': {msg}")

        return ParsedResponse(
            raw_text=raw_response,
            cleaned_json_text=cleaned_text,
            json_parsed=True,
            parsed_dict=parsed_dict,
            model_contract=None,
            is_valid_contract=False,
            is_malformed=True,
            errors=errors,
        )
