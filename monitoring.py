from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class UsageRecord:
    """Store token usage for one LLM request."""

    timestamp: str
    input_tokens: int
    output_tokens: int
    total_tokens: int


@dataclass
class UsageTracker:
    """
    Track aggregate token usage across LLM requests.

    Only token counts and safe metadata are stored.
    Source code and sensitive prompt contents are not logged.
    """

    records: list[UsageRecord] = field(
        default_factory=list
    )

    def record(
        self,
        input_tokens: int = 0,
        output_tokens: int = 0,
    ) -> UsageRecord:
        """Record token usage."""

        input_tokens = max(
            0,
            int(input_tokens),
        )

        output_tokens = max(
            0,
            int(output_tokens),
        )

        record = UsageRecord(
            timestamp=datetime.now(
                timezone.utc
            ).isoformat(),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=(
                input_tokens + output_tokens
            ),
        )

        self.records.append(record)

        return record

    @property
    def total_input_tokens(self) -> int:
        return sum(
            record.input_tokens
            for record in self.records
        )

    @property
    def total_output_tokens(self) -> int:
        return sum(
            record.output_tokens
            for record in self.records
        )

    @property
    def total_tokens(self) -> int:
        return (
            self.total_input_tokens
            + self.total_output_tokens
        )

    def summary(self) -> dict[str, int]:
        """Return aggregate token usage."""

        return {
            "requests": len(self.records),
            "input_tokens": (
                self.total_input_tokens
            ),
            "output_tokens": (
                self.total_output_tokens
            ),
            "total_tokens": self.total_tokens,
        }

    def clear(self) -> None:
        """Clear usage records."""

        self.records.clear()


def get_langsmith_config() -> dict[str, Any]:
    """
    Read LangSmith configuration from environment variables.

    No API key is returned by this function.
    """

    tracing_enabled = os.getenv(
        "LANGSMITH_TRACING",
        "false",
    ).lower() in {
        "true",
        "1",
        "yes",
        "on",
    }

    return {
        "tracing_enabled": tracing_enabled,
        "project": os.getenv(
            "LANGSMITH_PROJECT",
            "codebase-assistant",
        ),
        "endpoint": os.getenv(
            "LANGSMITH_ENDPOINT",
            "https://api.smith.langchain.com",
        ),
    }


def configure_langsmith() -> bool:
    """
    Configure LangSmith tracing through environment variables.

    Returns True when tracing is enabled and an API key exists.
    """

    config = get_langsmith_config()

    api_key = os.getenv(
        "LANGSMITH_API_KEY"
    )

    if not config["tracing_enabled"]:
        return False

    if not api_key:
        return False

    os.environ[
        "LANGSMITH_TRACING"
    ] = "true"

    os.environ[
        "LANGSMITH_PROJECT"
    ] = str(config["project"])

    os.environ[
        "LANGSMITH_ENDPOINT"
    ] = str(config["endpoint"])

    return True


def extract_token_usage(
    response: Any,
) -> tuple[int, int]:
    """
    Extract input and output token counts from a
    LangChain/Groq response when usage metadata exists.

    Returns:
        (input_tokens, output_tokens)
    """

    usage = getattr(
        response,
        "usage_metadata",
        None,
    )

    if not usage:
        response_metadata = getattr(
            response,
            "response_metadata",
            {},
        )

        usage = (
            response_metadata.get(
                "token_usage",
                {}
            )
            if isinstance(
                response_metadata,
                dict,
            )
            else {}
        )

    if not isinstance(
        usage,
        dict,
    ):
        return 0, 0

    input_tokens = usage.get(
        "input_tokens",
        usage.get(
            "prompt_tokens",
            0,
        ),
    )

    output_tokens = usage.get(
        "output_tokens",
        usage.get(
            "completion_tokens",
            0,
        ),
    )

    try:
        input_tokens = int(
            input_tokens or 0
        )
    except (
        TypeError,
        ValueError,
    ):
        input_tokens = 0

    try:
        output_tokens = int(
            output_tokens or 0
        )
    except (
        TypeError,
        ValueError,
    ):
        output_tokens = 0

    return (
        input_tokens,
        output_tokens,
    )


def create_usage_tracker() -> UsageTracker:
    """Create a new token usage tracker."""

    return UsageTracker()