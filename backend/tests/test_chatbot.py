"""Tests for the AI policy assistant. These never call OpenAI."""

import json

import pytest
from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.chatbot import (
    MockProvider,
    build_system_prompt,
    get_chat_provider,
    load_policy,
    parse_reply,
)
from app.config import get_settings
from app.database import get_db
from app.main import app
from app.models import User

# Stand-in for a logged-in employee, so these tests don't need a database.
TEST_USER = User(employee_id=1, name="Test Employee", email="test@example.com", role="employee")


class FakeProvider:
    """Returns a fixed reply and remembers what it was asked."""

    def __init__(self, reply: str = "", error: Exception | None = None) -> None:
        self.reply = reply
        self.error = error
        self.calls: list[tuple[str, str]] = []

    def complete(self, system_prompt: str, user_message: str) -> str:
        self.calls.append((system_prompt, user_message))
        if self.error:
            raise self.error
        return self.reply


@pytest.fixture()
def use_provider():
    """Swap in a provider for one test, then restore the app."""

    def _use(provider):
        app.dependency_overrides[get_chat_provider] = lambda: provider
        app.dependency_overrides[get_current_user] = lambda: TEST_USER
        return TestClient(app)

    yield _use
    app.dependency_overrides.clear()


def ask(client: TestClient, message: str):
    return client.post("/api/v1/ai/chat", json={"message": message})


# ---------------------------------------------------------------------------
# Prompt and policy
# ---------------------------------------------------------------------------


def test_policy_document_loads():
    assert "Global Campus Solutions" in load_policy()


def test_system_prompt_includes_policy_and_rules():
    prompt = build_system_prompt()

    assert "ONLY the PTO policy" in prompt
    assert "120 hours" in prompt  # a fact from the policy itself
    assert "requires_human_review" in prompt


# ---------------------------------------------------------------------------
# Successful answers
# ---------------------------------------------------------------------------


def test_chat_returns_answer_in_spec_format(use_provider):
    provider = FakeProvider(json.dumps({
        "answer": "Submit requests at least 7 calendar days before the start date.",
        "requires_human_review": False,
    }))
    client = use_provider(provider)

    response = ask(client, "How far in advance should I request PTO?")

    assert response.status_code == 200
    assert response.json() == {
        "response": "Submit requests at least 7 calendar days before the start date.",
        "source": "pto_policy_markdown",
        "requires_human_review": False,
    }


def test_question_is_sent_to_provider_with_policy_prompt(use_provider):
    provider = FakeProvider(json.dumps({"answer": "Yes.", "requires_human_review": False}))
    client = use_provider(provider)

    ask(client, "  Is Thanksgiving a holiday?  ")

    system_prompt, user_message = provider.calls[0]
    assert "PTO POLICY:" in system_prompt
    assert user_message == "Is Thanksgiving a holiday?"  # whitespace trimmed


def test_unanswerable_question_is_marked_for_human_review(use_provider):
    provider = FakeProvider(json.dumps({
        "answer": "The PTO policy doesn't cover sick leave. Please contact Human Resources.",
        "requires_human_review": True,
    }))
    client = use_provider(provider)

    response = ask(client, "How much sick leave do I get?")

    assert response.status_code == 200
    assert response.json()["requires_human_review"] is True


def test_mock_provider_returns_valid_answer(use_provider):
    client = use_provider(MockProvider())

    response = ask(client, "How much PTO do I get?")

    assert response.status_code == 200
    assert "120 hours" in response.json()["response"]


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_empty_message_returns_422(use_provider):
    client = use_provider(FakeProvider("{}"))

    response = ask(client, "   ")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_message_over_2000_characters_returns_422(use_provider):
    client = use_provider(FakeProvider("{}"))

    response = ask(client, "a" * 2001)

    assert response.status_code == 422


def test_message_of_exactly_2000_characters_is_allowed(use_provider):
    provider = FakeProvider(json.dumps({"answer": "OK.", "requires_human_review": False}))
    client = use_provider(provider)

    response = ask(client, "a" * 2000)

    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Failures and fallbacks
# ---------------------------------------------------------------------------


def test_provider_failure_returns_503_with_clear_message(use_provider):
    client = use_provider(FakeProvider(error=TimeoutError("timed out")))

    response = ask(client, "How much PTO do I get?")

    assert response.status_code == 503
    body = response.json()
    assert body["error"]["code"] == "AI_SERVICE_UNAVAILABLE"
    assert "timed out" not in response.text  # no internal details leaked


def test_empty_provider_reply_returns_503(use_provider):
    client = use_provider(FakeProvider(""))

    response = ask(client, "How much PTO do I get?")

    assert response.status_code == 503


def test_non_json_reply_is_returned_but_marked_for_review():
    result = parse_reply("Employees get 120 hours per year.")

    assert result.response == "Employees get 120 hours per year."
    assert result.requires_human_review is True


def test_missing_api_key_returns_503(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "ai_provider", "openai")
    monkeypatch.setattr(settings, "openai_api_key", "")
    app.dependency_overrides[get_current_user] = lambda: TEST_USER

    try:
        response = ask(TestClient(app), "How much PTO do I get?")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "AI_SERVICE_UNAVAILABLE"


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


def test_chat_requires_login():
    app.dependency_overrides[get_chat_provider] = lambda: MockProvider()
    app.dependency_overrides[get_db] = lambda: None  # no database needed to reject a missing token

    try:
        response = ask(TestClient(app), "How much PTO do I get?")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"
