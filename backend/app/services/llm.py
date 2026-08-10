"""
Unified LLM service interface supporting multiple providers:
- Anthropic (Claude)
- OpenAI (GPT models or OpenAI-compatible APIs like DeepSeek, Groq, OpenRouter)
- Google Gemini
- Ollama (running locally)
"""
from typing import Optional
import httpx

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


def get_llm_provider() -> Optional[str]:
    """Determine the active LLM provider based on config settings."""
    if settings.llm_provider:
        return settings.llm_provider.lower().strip()
    
    # Auto-detect based on configured credentials
    if settings.anthropic_api_key:
        return "anthropic"
    if settings.openai_api_key:
        return "openai"
    if settings.gemini_api_key:
        return "gemini"
    if settings.ollama_base_url and settings.ollama_model:
        return "ollama"
    return None


def llm_is_enabled() -> bool:
    """Check if any LLM integration is enabled."""
    return get_llm_provider() is not None


def llm_complete(prompt: str, json_mode: bool = False) -> str:
    """
    Send a prompt to the configured LLM provider and return the raw text response.
    """
    provider = get_llm_provider()
    if not provider:
        logger.warning("LLM request made but no LLM provider is configured.")
        return ""

    logger.info("Sending prompt to LLM provider: %s", provider)

    if provider == "anthropic":
        return _complete_anthropic(prompt)
    elif provider == "openai":
        return _complete_openai(prompt, json_mode)
    elif provider == "gemini":
        return _complete_gemini(prompt, json_mode)
    elif provider == "ollama":
        return _complete_ollama(prompt, json_mode)
    
    logger.error("Unknown LLM provider: %s", provider)
    return ""


def _complete_anthropic(prompt: str) -> str:
    from anthropic import Anthropic
    client = Anthropic(api_key=settings.anthropic_api_key)
    try:
        resp = client.messages.create(
            model=settings.anthropic_model or "claude-3-5-sonnet-20240620",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(b.text for b in resp.content if b.type == "text").strip()
    except Exception as exc:
        logger.error("Anthropic API error: %s", exc)
        return ""


def _complete_openai(prompt: str, json_mode: bool = False) -> str:
    api_key = settings.openai_api_key
    base_url = settings.openai_api_base.rstrip("/")
    model = settings.openai_model or "gpt-4o-mini"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
        "max_tokens": 200,
    }
    
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(f"{base_url}/chat/completions", headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        logger.error("OpenAI API error: %s", exc)
        return ""


def _complete_gemini(prompt: str, json_mode: bool = False) -> str:
    api_key = settings.gemini_api_key
    model = settings.gemini_model or "gemini-1.5-flash"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    headers = {"Content-Type": "application/json"}
    
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "temperature": 0.0,
            "maxOutputTokens": 200,
        }
    }
    
    if json_mode:
        payload["generationConfig"]["responseMimeType"] = "application/json"

    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as exc:
        logger.error("Gemini API error: %s", exc)
        return ""


def _complete_ollama(prompt: str, json_mode: bool = False) -> str:
    base_url = settings.ollama_base_url.rstrip("/")
    model = settings.ollama_model or "llama3"
    url = f"{base_url}/api/chat"

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {
            "temperature": 0.0,
        }
    }
    
    if json_mode:
        payload["format"] = "json"

    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["message"]["content"].strip()
    except Exception as exc:
        logger.error("Ollama API error: %s", exc)
        return ""
