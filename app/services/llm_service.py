import json
import os
from typing import Any

from dotenv import load_dotenv

from app.modules.copilot.prompts import INTENT_PROMPT_TEMPLATE


load_dotenv()


def get_llm() -> Any:
    """Create the Ollama-backed LangChain model used for intent parsing."""
    from langchain_ollama import OllamaLLM

    model_name = os.getenv("OLLAMA_MODEL", "gemma3:latest")
    return OllamaLLM(model=model_name, temperature=0.1)


def parse_intent_with_llm(query: str) -> dict[str, Any]:
    """Ask the local LLM to convert recruiter text into JSON filter intent."""
    from langchain_core.prompts import PromptTemplate

    prompt = PromptTemplate.from_template(INTENT_PROMPT_TEMPLATE)
    chain = prompt | get_llm()
    raw_response = chain.invoke({"query": query})
    return _extract_json(raw_response)


def _extract_json(text: str) -> dict[str, Any]:
    """Extract the first JSON object from an LLM response."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").replace("json", "", 1).strip()

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("LLM did not return a JSON object.")

    return json.loads(cleaned[start : end + 1])
