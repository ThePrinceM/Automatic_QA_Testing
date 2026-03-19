"""
LLM Engine — LangChain integration layer.
Provides an interface to Google Gemini models
with retry logic and structured output helpers.
"""

import time
import json
import logging
from typing import Any

from langchain_core.prompts import ChatPromptTemplate

import config

logger = logging.getLogger(__name__)


def get_llm():
    """
    Create a LangChain LLM instance based on configured provider.
    
    Supports:
    - Gemini (Google)
    - OpenRouter (multiple models)
    
    Returns:
        BaseChatModel: A LangChain chat model instance.
    
    Raises:
        EnvironmentError: If required API key is missing.
    """
    config.validate_config()

    if config.LLM_PROVIDER == "openrouter":
        from langchain_openai import ChatOpenAI
        logger.info(f"Initializing OpenRouter LLM: {config.MODEL_NAME}")
        return ChatOpenAI(
            model=config.MODEL_NAME,
            api_key=config.OPENROUTER_API_KEY,
            base_url=config.OPENROUTER_BASE_URL,
            temperature=config.LLM_TEMPERATURE,
        )
    else:  # Default to Gemini
        from langchain_google_genai import ChatGoogleGenerativeAI
        logger.info(f"Initializing Google Gemini LLM: {config.MODEL_NAME}")
        return ChatGoogleGenerativeAI(
            model=config.MODEL_NAME,
            google_api_key=config.GOOGLE_API_KEY,
            temperature=config.LLM_TEMPERATURE,
            convert_system_message_to_human=True,
        )



def invoke_chain(
    prompt: ChatPromptTemplate,
    variables: dict[str, Any],
    retries: int | None = None,
) -> str:
    """
    Build a LangChain chain (prompt | llm) and invoke it with retry logic.
    
    Args:
        prompt: A LangChain ChatPromptTemplate.
        variables: Template variables dict.
        retries: Number of retries on failure (defaults to config).
        
    Returns:
        str: The raw text content from the LLM response.
    """
    max_retries = retries if retries is not None else config.LLM_MAX_RETRIES
    llm = get_llm()
    chain = prompt | llm

    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            logger.debug(f"LLM invocation attempt {attempt}/{max_retries}")
            result = chain.invoke(variables)
            content = result.content if hasattr(result, "content") else str(result)
            logger.debug(f"LLM response length: {len(content)} chars")
            return content
        except Exception as e:
            last_error = e
            logger.warning(f"LLM call failed (attempt {attempt}/{max_retries}): {e}")
            if attempt < max_retries:
                wait_time = 2 ** attempt
                logger.info(f"Retrying in {wait_time}s...")
                time.sleep(wait_time)

    raise RuntimeError(
        f"LLM invocation failed after {max_retries} attempts. Last error: {last_error}"
    )


def invoke_chain_json(
    prompt: ChatPromptTemplate,
    variables: dict[str, Any],
    retries: int | None = None,
) -> dict | list:
    """
    Invoke a chain and parse the response as JSON.
    Handles common LLM quirks like markdown-fenced JSON.
    
    Returns:
        Parsed JSON as dict or list.
    """
    raw = invoke_chain(prompt, variables, retries)
    
    # Strip markdown code fences if present
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        # Remove first line (```json) and last line (```)
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines)
    
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM JSON response: {e}")
        logger.debug(f"Raw response:\n{raw}")
        raise ValueError(f"LLM returned invalid JSON: {e}") from e
