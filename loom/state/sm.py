"""FDE session state machine."""
from __future__ import annotations

from enum import StrEnum


class SessionState(StrEnum):
    INIT = "init"
    LLM_CONFIG_SET = "llm_config_set"
    DRAFTING = "drafting"
    VALIDATED = "validated"
    COMPILED = "compiled"
    DOWNLOADED = "downloaded"


class IllegalTransition(ValueError):
    """Raised when a session event is invalid for the current state."""


_TRANSITIONS: dict[tuple[SessionState, str], SessionState] = {
    (SessionState.INIT, "llm_config_set"): SessionState.LLM_CONFIG_SET,
    (SessionState.INIT, "turn_started"): SessionState.DRAFTING,
    (SessionState.LLM_CONFIG_SET, "turn_started"): SessionState.DRAFTING,
    (SessionState.DRAFTING, "turn_succeeded"): SessionState.VALIDATED,
    (SessionState.DRAFTING, "turn_failed"): SessionState.LLM_CONFIG_SET,
    (SessionState.VALIDATED, "turn_started"): SessionState.DRAFTING,
    (SessionState.VALIDATED, "compile_succeeded"): SessionState.COMPILED,
    (SessionState.COMPILED, "compile_succeeded"): SessionState.COMPILED,
    (SessionState.COMPILED, "artifact_downloaded"): SessionState.DOWNLOADED,
    (SessionState.DOWNLOADED, "turn_started"): SessionState.DRAFTING,
    (SessionState.DOWNLOADED, "compile_succeeded"): SessionState.COMPILED,
}


def transition(state: SessionState | str, event: str) -> SessionState:
    current = SessionState(state)
    try:
        return _TRANSITIONS[(current, event)]
    except KeyError as e:
        raise IllegalTransition(f"cannot apply {event!r} from {current.value!r}") from e
