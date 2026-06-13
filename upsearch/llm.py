"""
LLM abstraction layer — routes calls to Claude Opus 4.8, DeepSeek, or OpenRouter.
Switch provider by setting MODEL_PROVIDER=claude, MODEL_PROVIDER=deepseek, or
MODEL_PROVIDER=openrouter in .env.
"""
import os

PROVIDER = os.environ.get("MODEL_PROVIDER", "claude").lower()

# Model identifiers
CLAUDE_MODEL = "claude-opus-4-8"
DEEPSEEK_MODEL = "deepseek-chat"  # or "deepseek-reasoner" for harder reasoning tasks
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "deepseek/deepseek-chat")


def _claude_client():
    import anthropic
    return anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))


def _deepseek_client():
    from openai import OpenAI
    return OpenAI(
        api_key=os.environ.get("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com/v1",
    )


def _openrouter_client():
    from openai import OpenAI
    return OpenAI(
        api_key=os.environ.get("OPENROUTER_API_KEY"),
        base_url="https://openrouter.ai/api/v1",
    )


def _openai_compatible_route():
    """(client, model) for OpenAI-compatible providers, or None for Claude."""
    if PROVIDER == "deepseek":
        return _deepseek_client(), DEEPSEEK_MODEL
    if PROVIDER == "openrouter":
        return _openrouter_client(), OPENROUTER_MODEL
    return None


def complete(system: str, user: str, max_tokens: int = 1024) -> str:
    """
    Single-turn completion. Returns the assistant response as a plain string.
    Works identically regardless of provider.
    """
    compat = _openai_compatible_route()
    if compat:
        client, model = compat
        response = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return (response.choices[0].message.content or "").strip()

    else:
        # Default: Claude with prompt caching on the system prompt
        client = _claude_client()
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=max_tokens,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user}],
        )
        return response.content[0].text.strip()


def complete_with_tools(system: str, user: str, tools: list, max_tokens: int = 1024):
    """
    Tool-use completion for the Scout agent.
    Returns the raw response object (provider-specific) alongside parsed tool calls.

    Returns: (tool_calls, stop_reason, raw_response)
      tool_calls: list of dicts {"name": str, "input": dict, "id": str}
      stop_reason: "tool_use" | "end_turn" | "stop"
    """
    compat = _openai_compatible_route()
    if compat:
        import json

        client, model = compat

        # Convert Anthropic tool schema to OpenAI format
        oai_tools = [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["input_schema"],
                },
            }
            for t in tools
        ]

        response = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            tools=oai_tools,
            tool_choice="auto",
        )

        choice = response.choices[0]
        tool_calls = []
        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                tool_calls.append({
                    "name": tc.function.name,
                    "input": json.loads(tc.function.arguments),
                    "id": tc.id,
                })

        stop_reason = "tool_use" if tool_calls else "end_turn"
        return tool_calls, stop_reason, response

    else:
        import anthropic
        client = _claude_client()
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=max_tokens,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            tools=tools,
            messages=[{"role": "user", "content": user}],
        )

        tool_calls = []
        for block in response.content:
            if block.type == "tool_use":
                tool_calls.append({
                    "name": block.name,
                    "input": block.input,
                    "id": block.id,
                })

        stop_reason = "tool_use" if tool_calls else "end_turn"
        return tool_calls, stop_reason, response


def make_tool_result_message(tool_calls: list, results: list[str], raw_response) -> list[dict]:
    """
    Build the follow-up messages after tool calls, in the correct format for the active provider.
    """
    if PROVIDER in {"deepseek", "openrouter"}:
        messages = []
        # Re-add assistant message with tool calls
        choice = raw_response.choices[0]
        messages.append({
            "role": "assistant",
            "content": choice.message.content or "",
            "tool_calls": [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {"name": tc["name"], "arguments": str(tc["input"])},
                }
                for tc in tool_calls
            ],
        })
        for tc, result in zip(tool_calls, results):
            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": result,
            })
        return messages

    else:
        # Anthropic format — returns (assistant_content, user_tool_results)
        return [raw_response.content, tool_calls, results]


def active_provider() -> str:
    return PROVIDER


def active_model() -> str:
    if PROVIDER == "deepseek":
        return DEEPSEEK_MODEL
    if PROVIDER == "openrouter":
        return OPENROUTER_MODEL
    return CLAUDE_MODEL
