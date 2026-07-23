"""Optional web-task agent via browser-use (https://github.com/browser-use/browser-use).

Experimental. Requires:
    pip install browser-use && playwright install chromium
    JARVIS_ENABLE_WEBTASK=1

Reuses the same OpenAI-compatible gateway (OpenRouter / OmniRoute) configured
for the brain. Honest caveat: browser-use needs a *capable* model to be
reliable; small free-tier models will fumble multi-step web tasks.
"""

import os

from ..config import settings


def is_enabled() -> bool:
    return os.environ.get("JARVIS_ENABLE_WEBTASK", "").strip().lower() in ("1", "true", "yes")


async def run_web_task(task: str) -> str:
    if not is_enabled():
        raise RuntimeError("Web tasks disabled. Set JARVIS_ENABLE_WEBTASK=1 to enable.")
    try:
        from browser_use import Agent
    except ImportError as exc:
        raise RuntimeError(
            "browser-use not installed. Run: pip install browser-use && playwright install chromium"
        ) from exc

    llm = _build_llm()
    agent = Agent(task=task, llm=llm)
    history = await agent.run()
    result = getattr(history, "final_result", None)
    if callable(result):
        result = result()
    return str(result or history)


def _build_llm():
    # browser-use moved its LLM wrappers around between versions; try the
    # modern location first, then the legacy langchain one.
    try:
        from browser_use.llm import ChatOpenAI  # browser-use >= 0.3

        return ChatOpenAI(
            model=settings.llm_model,
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key or "local",
        )
    except ImportError:
        from langchain_openai import ChatOpenAI  # older browser-use

        return ChatOpenAI(
            model=settings.llm_model,
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key or "local",
        )
