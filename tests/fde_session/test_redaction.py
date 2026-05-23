from loom.fde_session.brief import WorkflowBriefDraft
from loom.fde_session.redaction import redact_draft, redact_text


def test_redact_draft_scrubs_secret_like_intent_text() -> None:
    draft = WorkflowBriefDraft(
        title="Secret test",
        intent="use Bearer sk_test_abc1234567890abcdef please",
        success_criteria="Keep responses grounded.",
    )

    redacted = redact_draft(draft)

    assert redacted.intent == "[REDACTED]"
    assert "sk_test" not in (redacted.intent or "")
    assert "abc1234567890abcdef" not in (redacted.intent or "")


def test_redact_text_is_idempotent() -> None:
    first = redact_text("Authorization: Bearer abc1234567890abcdef")

    assert first == "[REDACTED]"
    assert redact_text(first) == first
