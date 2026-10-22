"""The one place where tennis-scout calls a language model, through OpenRouter.

The model only writes text around numbers it is given. To switch models, change MODEL below.
The key is read from the OPENROUTER_API_KEY environment variable (from .env locally, from the
project settings on Vercel). It is never printed or logged.
"""

import os

from dotenv import load_dotenv
from openai import APIStatusError, OpenAI, RateLimitError

MODEL = "mistralai/mistral-medium-3-5"  # Mistral Medium 3.5: chosen after the model comparison (DECISIONS.md)
MAX_TOKENS = 2000        # the model writes only short headlines and fact IDs (well under 1,000 tokens)
# Some models "think" before writing, and on OpenRouter those thinking tokens count against MAX_TOKENS.
# In testing, Mistral Large 4 used all its tokens thinking and returned an empty report. "none" turns it off.
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


def write_report(messages, model=MODEL, reasoning_effort=REASONING_EFFORT, max_tokens=MAX_TOKENS,
                 response_format=None):
    """Send the messages to the model; return the text and what the call used (tokens, cost in US dollars).

    The website always uses the defaults. Only scripts/check_reports.py passes other values, to compare models
    before launch (some models, such as Claude Sonnet 5.5, cannot turn their thinking off).
    response_format: optional, a JSON schema the reply must follow (the website asks for headlines this way).
    """
    try:
        # Temperature 0 (least creative) only without thinking: Anthropic models refuse it when thinking is on.
        options = {"temperature": 0} if reasoning_effort == "none" else {}
        if response_format:
            options["response_format"] = response_format
        response = _client().chat.completions.create(
            model=model, messages=messages, max_tokens=max_tokens, **options,
            extra_body={"reasoning": {"effort": reasoning_effort}},  # an OpenRouter option, not in the OpenAI SDK
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
        "cost_usd": getattr(response.usage, "cost", None),  # OpenRouter adds the real cost of the call here
    }
