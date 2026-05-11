import pytest

from loom.state.sm import IllegalTransition, SessionState, transition


def test_session_state_happy_path():
    state = SessionState.INIT
    state = transition(state, "llm_config_set")
    state = transition(state, "turn_started")
    state = transition(state, "turn_succeeded")
    state = transition(state, "compile_succeeded")
    state = transition(state, "artifact_downloaded")
    assert state == SessionState.DOWNLOADED


def test_illegal_transition_rejected():
    with pytest.raises(IllegalTransition):
        transition(SessionState.INIT, "compile_succeeded")
