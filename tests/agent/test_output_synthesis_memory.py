import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.mark.asyncio
async def test_output_synthesizer_memory_applied(caplog, mock_output_synthesizer, mock_context, monkeypatch):
    caplog.set_level("DEBUG")

    # Mock synthesize_memory to return insights
    async def mock_synthesize_memory(past_context, llm_client):
        return {
            "communication_style": "direct",
            "preferences": "concise",
            "recurring_topics": "metrics",
            "open_loops": "follow-up items",
        }

    monkeypatch.setattr("app.tools.memory_processing.synthesize_memory", mock_synthesize_memory)

    tool_output = {"tool_name": "summarization", "result": {"summary": "Original summary"}}

    result = await mock_output_synthesizer.synthesize(
        message="Test message",
        intent="summarization",
        tool_output=tool_output,
        context=mock_context,
    )

    # Ensure memory-aware framing applied (result is rephrased; we only check that it's a string and not empty)
    assert isinstance(result, str)
    assert result != ""

    # Logging includes memory insights
    assert any("memory insights computed" in rec.message for rec in caplog.records)

    # Original tool result preserved as source; since we rephrase, ensure original summary remains unchanged in tool_output
    assert tool_output["result"]["summary"] == "Original summary"


@pytest.mark.asyncio
async def test_output_synthesizer_no_memory(caplog, mock_output_synthesizer):
    caplog.set_level("DEBUG")

    tool_output = {"tool_name": "summarization", "result": {"summary": "Original summary"}}

    result = await mock_output_synthesizer.synthesize(
        message="Test message",
        intent="summarization",
        tool_output=tool_output,
        context=None,
    )

    # Should return original summary when no memory
    assert result == "Original summary"

    # No memory logs
    assert not any("memory insights computed" in rec.message for rec in caplog.records)

