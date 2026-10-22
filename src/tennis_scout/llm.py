"""The one place where tennis-scout calls a language model, through OpenRouter.

The model only writes text around numbers it is given. To switch models, change MODEL below.
The key is read from the OPENROUTER_API_KEY environment variable (from .env locally, from the
project settings on Vercel). It is never printed or logged.
"""

import os

from dotenv import load_dotenv
from openai import APIStatusError, OpenAI, RateLimitError

MODEL = "mistralai/mistral-large-4-0"  # Mistral Large 4 (Mistral Small 4 failed the pre-launch check)
MAX_TOKENS = 3000        # a report is about 2,000 tokens; this caps the cost of one reply
# Mistral Large 4 can "think" before writing, and on OpenRouter those thinking tokens count against MAX_TOKENS.
# With thinking on, it used all 3,000 tokens thinking and returned an empty report. "none" turns it off.
REASONING_EFFORT = "none"
TIMEOUT_SECONDS = 50     # the website function stops after 60 seconds
OPENROUTER_URL = "https://openrouter.ai/api/v1"


class BudgetUsedUp(Exception):
    """OpenRouter refused the call because the key's credit limit is reached."""


class ModelBusy(Exception):
    """The model is rate-limited for now (by OpenRouter or by the model's provider). Trying later usually works."""


class EmptyReply(Exception):
    """The model returned no text (for example, it hit MAX_TOKENS before writing anything)."""


def _client():
    load_dotenv()  # local runs only: reads .env if there is one (it does not override a variable already set)
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is not set (in .env locally, in the project settings on Vercel).")
    # max_retries=1: one retry at most, for network errors and temporary server errors.
    return OpenAI(base_url=OPENROUTER_URL, api_key=key, timeout=TIMEOUT_SECONDS, max_retries=1)


def write_report(messages, model=MODEL):
    """Send the messages to the model; return the text and what the call used.

    The website always uses MODEL. Only scripts/check_reports.py passes another model, to compare models before launch.
    """
    try:
        response = _client().chat.completions.create(
            model=model, messages=messages, max_tokens=MAX_TOKENS, temperature=0,  # temperature 0: least creative
            extra_body={"reasoning": {"effort": REASONING_EFFORT}},  # an OpenRouter option, not in the OpenAI SDK
        )
    except RateLimitError as error:  # 429, for example "temporarily rate-limited upstream"
        raise ModelBusy("The model is busy right now. Please try again in a minute.") from error
    except APIStatusError as error:
        # OpenRouter answers 402 or 403 (openrouter_key_limit) when the key's credit limit is used up.
        if error.status_code in (402, 403):
            raise BudgetUsedUp("The report budget is used up. Please try again later.") from error
        raise
    choice = response.choices[0]
    if not (choice.message.content or "").strip():
        raise EmptyReply(f"The model returned an empty report (finish reason: {choice.finish_reason}).")
    details = getattr(response.usage, "completion_tokens_details", None)
    return {
        "text": choice.message.content,
        "finish_reason": choice.finish_reason,  # "length" means the reply hit MAX_TOKENS and was cut
        "model": response.model,
        "input_tokens": response.usage.prompt_tokens,
        "output_tokens": response.usage.completion_tokens,
        "reasoning_tokens": getattr(details, "reasoning_tokens", None) or 0,  # part of output_tokens
    }
