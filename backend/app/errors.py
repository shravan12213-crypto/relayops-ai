"""Application error definitions and error envelope helpers."""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Raised by application code to produce the standard error envelope."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class LLMError(AppError):
    def __init__(
        self,
        message: str,
        code: str = "LLM_ERROR",
        status_code: int = 500,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(code=code, message=message, status_code=status_code, details=details)


class LLMOutputError(LLMError):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(code="LLM_OUTPUT_ERROR", message=message, status_code=502, details=details)


class LLMReplayMissError(LLMError):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(code="LLM_REPLAY_MISS", message=message, status_code=500, details=details)


class LLMBudgetError(LLMError):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(code="LLM_BUDGET_EXCEEDED", message=message, status_code=429, details=details)
