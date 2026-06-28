"""Unit tests for ValueResolver."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))

from sop_automation.errors import ValueResolutionError
from sop_automation.runtime.value_resolver import ValueResolver


@pytest.fixture()
def resolver() -> ValueResolver:
    return ValueResolver()


@pytest.fixture()
def context() -> dict:
    return {
        "inputs": {"email": "user@example.com", "url": "https://app.example.com"},
        "outputs": {"contact_id": "12345"},
        "steps": {
            "step_001": {
                "value": "clicked",
                "text": "Submit",
                "current_url": "https://app.example.com/dashboard",
            }
        },
    }


class TestResolveNone:
    def test_none_value_returns_none(self, resolver, context):
        assert resolver.resolve(None, context) is None


class TestNoPlaceholders:
    def test_plain_string_returned_as_is(self, resolver, context):
        assert resolver.resolve("hello world", context) == "hello world"

    def test_url_string_returned_as_is(self, resolver, context):
        assert resolver.resolve("https://example.com", context) == "https://example.com"


class TestInputPlaceholders:
    def test_single_input_placeholder(self, resolver, context):
        assert resolver.resolve("{{input.email}}", context) == "user@example.com"

    def test_single_input_url_placeholder(self, resolver, context):
        assert resolver.resolve("{{input.url}}", context) == "https://app.example.com"

    def test_embedded_input_placeholder_produces_string(self, resolver, context):
        result = resolver.resolve("mailto:{{input.email}}", context)
        assert result == "mailto:user@example.com"

    def test_missing_input_raises(self, resolver, context):
        with pytest.raises(ValueResolutionError, match="not found"):
            resolver.resolve("{{input.missing_key}}", context)


class TestOutputPlaceholders:
    def test_single_output_placeholder(self, resolver, context):
        assert resolver.resolve("{{output.contact_id}}", context) == "12345"

    def test_missing_output_raises(self, resolver, context):
        with pytest.raises(ValueResolutionError):
            resolver.resolve("{{output.no_such_output}}", context)


class TestStepPlaceholders:
    def test_step_value_placeholder(self, resolver, context):
        assert resolver.resolve("{{steps.step_001.value}}", context) == "clicked"

    def test_step_text_placeholder(self, resolver, context):
        assert resolver.resolve("{{steps.step_001.text}}", context) == "Submit"

    def test_step_current_url_placeholder(self, resolver, context):
        result = resolver.resolve("{{steps.step_001.current_url}}", context)
        assert result == "https://app.example.com/dashboard"

    def test_missing_step_raises(self, resolver, context):
        with pytest.raises(ValueResolutionError, match="not found"):
            resolver.resolve("{{steps.nonexistent.value}}", context)

    def test_missing_step_field_raises(self, resolver, context):
        with pytest.raises(ValueResolutionError):
            resolver.resolve("{{steps.step_001.no_such_field}}", context)


class TestEmbeddedPlaceholders:
    def test_multiple_placeholders_in_string(self, resolver, context):
        result = resolver.resolve("{{input.email}} at {{input.url}}", context)
        assert result == "user@example.com at https://app.example.com"

    def test_embedded_returns_string_type(self, resolver, context):
        result = resolver.resolve("id={{output.contact_id}}", context)
        assert isinstance(result, str)
        assert result == "id=12345"


class TestInvalidSyntax:
    def test_invalid_namespace_raises(self, resolver, context):
        with pytest.raises(ValueResolutionError):
            resolver.resolve("{{unknown.something}}", context)

    def test_too_short_key_raises(self, resolver, context):
        with pytest.raises(ValueResolutionError):
            resolver.resolve("{{input}}", context)
