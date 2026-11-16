"""Run one agent with the Claude Agent SDK: our tools only, schema-validated output, full transcript."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

DEFAULT_MODEL = "claude-opus-5-5"


def default_model() -> str:
    return os.environ.get("VALUER_MODEL", DEFAULT_MODEL)


class AgentError(RuntimeError):
    pass


@dataclass
class AgentResult:
    output: dict
    models: list[str]
    cost_usd: float | None = None
    turns: int = 0
    transcript: list[dict] = field(default_factory=list)


async def run_agent(name: str, system_prompt: str, prompt: str, server: Any, allowed_tools: list[str],
                    schema: type[BaseModel], model: str, max_turns: int = 80) -> AgentResult:
    from claude_agent_sdk import (AssistantMessage, ClaudeAgentOptions, ResultMessage, TextBlock, ToolResultBlock,
                                  ToolUseBlock, UserMessage, query)

    options = ClaudeAgentOptions(
        model=model,
        system_prompt=system_prompt,
        tools=[],  # no built-in tools: no shell, no files, no web
        mcp_servers={"valuer": server},
        allowed_tools=allowed_tools,
        strict_mcp_config=True,
        setting_sources=[],  # ignore any local Claude Code settings, skills and memory
        permission_mode="dontAsk",
        max_turns=max_turns,
        output_format={"type": "json_schema", "schema": schema.model_json_schema()},
    )
    transcript: list[dict] = []
    models: set[str] = set()
    result: ResultMessage | None = None
    async for msg in query(prompt=prompt, options=options):
        if isinstance(msg, AssistantMessage):
            models.add(msg.model)
            for b in msg.content:
                if isinstance(b, TextBlock):
                    transcript.append({"agent": name, "type": "text", "text": b.text})
                elif isinstance(b, ToolUseBlock):
                    transcript.append({"agent": name, "type": "tool_call", "tool": b.name, "input": b.input})
        elif isinstance(msg, UserMessage) and isinstance(msg.content, list):
            for b in msg.content:
                if isinstance(b, ToolResultBlock):
                    text = b.content if isinstance(b.content, str) else " ".join(
                        c.get("text", "") for c in (b.content or []) if isinstance(c, dict))
                    transcript.append({"agent": name, "type": "tool_result", "chars": len(text), "head": text[:500]})
        elif isinstance(msg, ResultMessage):
            result = msg
    if result is None:
        raise AgentError(f"{name}: the agent ended without a result")
    if result.is_error or result.structured_output is None:
        raise AgentError(f"{name}: {result.subtype}; errors={result.errors}; text={(result.result or '')[:300]}")
    try:
        output = schema.model_validate(result.structured_output).model_dump()
    except Exception as exc:
        raise AgentError(f"{name}: output failed schema validation: {exc}") from exc
    served = sorted(set(result.model_usage or {}) | models)
    return AgentResult(output=output, models=served, cost_usd=result.total_cost_usd, turns=result.num_turns,
                       transcript=transcript)
