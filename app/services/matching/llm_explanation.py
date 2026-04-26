import asyncio
import importlib
import json
import os
import threading
from typing import Any

import httpx
from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()
os.environ.setdefault("PYDANTIC_AI_GATEWAY_BASE_URL", "https://gateway-eu.pydantic.dev/proxy")

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
PYDANTIC_GATEWAY_CHAT_URL = "https://gateway-eu.pydantic.dev/proxy/chat/completions"
DEFAULT_MODEL = "gateway/google-vertex:gemini-2.5-flash"
GATEWAY_LOOP = asyncio.new_event_loop()
GATEWAY_LOOP_LOCK = threading.Lock()


class LLMExplanation(BaseModel):
    explanation: str
    positive_signals: list[str] = Field(default_factory=list)
    negative_signals: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)


class LLMExplanationResult(BaseModel):
    status: str
    model: str | None = None
    explanation: LLMExplanation | None = None
    warning: str | None = None


def generate_llm_explanation(evidence: dict[str, Any]) -> LLMExplanationResult:
    api_key = _api_key()
    model = os.getenv("MATCHING_LLM_MODEL", DEFAULT_MODEL)
    if not api_key:
        return _unavailable_result("PYDANTIC_AI_GATEWAY_API_KEY or OPENAI_API_KEY is not configured.", model)
    if model.startswith("gateway/"):
        return _call_pydantic_ai_gateway(model, evidence)
    if os.getenv("PYDANTIC_AI_GATEWAY_API_KEY"):
        return _call_gateway_chat(api_key, model, evidence, _gateway_chat_url())
    return _call_openai(api_key, model, evidence, _responses_url())


def _call_pydantic_ai_gateway(model: str, evidence: dict[str, Any]) -> LLMExplanationResult:
    try:
        agent_class = _pydantic_ai_agent_class()
        agent = agent_class(model, instructions=_instructions(), output_type=LLMExplanation)
        result = _run_agent(agent, json.dumps(evidence, default=str))
    except Exception as exc:
        return _unavailable_result(f"Pydantic AI Gateway explanation request failed: {exc}", model)
    return _pydantic_ai_result(result, model)


def _call_gateway_chat(api_key: str, model: str, evidence: dict[str, Any], chat_url: str) -> LLMExplanationResult:
    try:
        response = httpx.post(chat_url, headers=_headers(api_key), json=_chat_payload(model, evidence), timeout=30)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        return _unavailable_result(f"Pydantic AI Gateway explanation request failed: {exc}", model)
    return _parse_chat_response(response.json(), model)


def _call_openai(api_key: str, model: str, evidence: dict[str, Any], responses_url: str) -> LLMExplanationResult:
    try:
        response = httpx.post(responses_url, headers=_headers(api_key), json=_payload(model, evidence), timeout=30)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        return _unavailable_result(f"LLM explanation request failed: {exc}", model)
    return _parse_response(response.json(), model)


def _pydantic_ai_agent_class() -> Any:
    pydantic_ai = importlib.import_module("pydantic_ai")
    return getattr(pydantic_ai, "Agent")


def _run_agent(agent: Any, prompt: str) -> Any:
    with GATEWAY_LOOP_LOCK:
        return GATEWAY_LOOP.run_until_complete(agent.run(prompt))


def _pydantic_ai_result(result: Any, model: str) -> LLMExplanationResult:
    output = getattr(result, "output", None) or getattr(result, "data", None)
    if isinstance(output, LLMExplanation):
        return LLMExplanationResult(status="completed", model=model, explanation=output)
    return _unavailable_result("Pydantic AI Gateway response did not include structured explanation output.", model)


def _payload(model: str, evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "model": model,
        "instructions": _instructions(),
        "input": [{"role": "user", "content": json.dumps(evidence, default=str)}],
        "text": {"format": _json_schema()},
    }


def _chat_payload(model: str, evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "model": model,
        "prompt": _completion_prompt(evidence),
    }


def _headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def _api_key() -> str | None:
    return os.getenv("PYDANTIC_AI_GATEWAY_API_KEY") or os.getenv("OPENAI_API_KEY")


def _responses_url() -> str:
    return os.getenv("OPENAI_RESPONSES_URL", OPENAI_RESPONSES_URL)


def _gateway_chat_url() -> str:
    explicit_url = os.getenv("PYDANTIC_AI_GATEWAY_CHAT_URL")
    if explicit_url:
        return explicit_url
    base_url = os.getenv("PYDANTIC_AI_GATEWAY_BASE_URL")
    if base_url:
        return _gateway_chat_url_from_base(base_url)
    return PYDANTIC_GATEWAY_CHAT_URL


def _gateway_chat_url_from_base(base_url: str) -> str:
    stripped_url = base_url.rstrip("/")
    if stripped_url.endswith("/chat/completions"):
        return stripped_url
    if stripped_url.endswith("/chat"):
        return f"{stripped_url}/completions"
    return f"{stripped_url}/chat/completions"


def _instructions() -> str:
    return (
        "You are a senior VC analyst evaluating a VC-founder match. "
        "Write a single dense paragraph (150–250 words) in 'explanation' covering: "
        "stage fit, sector/thesis alignment, geography, notable portfolio companies the founder could partner with or that compete, "
        "relevant team expertise, and what would improve the fit. "
        "Cite specific names, companies, and numbers from the evidence — do not invent facts. "
        "If score band is poor_fit or weak_fit, lead with the weakest components. "
        "If competitor_penalty > 0 or max_competition_risk_score >= 70, open with the competitor risk and name the specific companies. "
        "Then populate positive_signals (3–5 concrete bullets), negative_signals (2–4 bullets), and risks (1–3 bullets). "
        "Return valid JSON only."
    )


def _completion_prompt(evidence: dict[str, Any]) -> str:
    return (
        f"{_instructions()}\n\n"
        "Return only valid JSON with keys: explanation, positive_signals, negative_signals, risks.\n\n"
        f"Evidence:\n{json.dumps(evidence, default=str)}"
    )


def _json_schema() -> dict[str, Any]:
    return {
        "type": "json_schema",
        "name": "vc_match_explanation",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "explanation": {"type": "string"},
                "positive_signals": {"type": "array", "items": {"type": "string"}},
                "negative_signals": {"type": "array", "items": {"type": "string"}},
                "risks": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["explanation", "positive_signals", "negative_signals", "risks"],
        },
    }


def _parse_response(response_json: dict[str, Any], model: str) -> LLMExplanationResult:
    output_text = _output_text(response_json)
    if not output_text:
        return _unavailable_result("LLM response did not include output text.", model)
    return LLMExplanationResult(status="completed", model=model, explanation=LLMExplanation.model_validate_json(output_text))


def _parse_chat_response(response_json: dict[str, Any], model: str) -> LLMExplanationResult:
    output_text = _chat_output_text(response_json)
    if not output_text:
        return _unavailable_result("Pydantic AI Gateway response did not include output text.", model)
    return LLMExplanationResult(status="completed", model=model, explanation=LLMExplanation.model_validate_json(output_text))


def _chat_output_text(response_json: dict[str, Any]) -> str | None:
    choices = response_json.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        return None
    if first_choice.get("text"):
        return str(first_choice["text"])
    message = first_choice.get("message")
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    if not content:
        return None
    return str(content)


def _output_text(response_json: dict[str, Any]) -> str | None:
    direct_text = response_json.get("output_text")
    if direct_text:
        return str(direct_text)
    return _nested_output_text(response_json.get("output"))


def _nested_output_text(output_items: Any) -> str | None:
    if not isinstance(output_items, list):
        return None
    for output_item in output_items:
        text_value = _text_from_output_item(output_item)
        if text_value:
            return text_value
    return None


def _text_from_output_item(output_item: Any) -> str | None:
    if not isinstance(output_item, dict):
        return None
    content_items = output_item.get("content")
    if not isinstance(content_items, list):
        return None
    return _text_from_content_items(content_items)


def _text_from_content_items(content_items: list[Any]) -> str | None:
    for content_item in content_items:
        if isinstance(content_item, dict) and content_item.get("text"):
            return str(content_item["text"])
    return None


def _unavailable_result(warning: str, model: str | None = None) -> LLMExplanationResult:
    return LLMExplanationResult(status="unavailable", model=model, warning=warning)
