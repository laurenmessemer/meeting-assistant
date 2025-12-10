import pytest


@pytest.mark.asyncio
async def test_workflow_planner_no_memory(monkeypatch, mock_llm):
    from app.orchestrator.workflow_planning import WorkflowPlanner

    planner = WorkflowPlanner(mock_llm)

    captured_prompt = {}

    def fake_llm_chat(prompt, system_prompt, response_format, temperature):
        captured_prompt["prompt"] = prompt
        return {"steps": [{"action": "summarize", "tool": "summarization"}]}

    mock_llm.llm_chat.side_effect = fake_llm_chat

    plan = await planner.plan("summarization", "msg", 1, 2, context=None)

    assert "prompt" in captured_prompt
    assert "User Context / Memory" not in captured_prompt["prompt"]
    assert isinstance(plan, dict)
    assert isinstance(plan.get("steps"), list)


@pytest.mark.asyncio
async def test_workflow_planner_with_memory(monkeypatch, mock_llm):
    from app.orchestrator.workflow_planning import WorkflowPlanner

    planner = WorkflowPlanner(mock_llm)

    def fake_synthesize_memory(past_context, llm_client):
        return {"communication_style": "direct", "preferences": "concise"}

    monkeypatch.setattr("app.tools.memory_processing.synthesize_memory", fake_synthesize_memory)

    captured_prompt = {}

    def fake_llm_chat(prompt, system_prompt, response_format, temperature):
        captured_prompt["prompt"] = prompt
        return {"steps": [{"action": "summarize", "tool": "summarization"}]}

    mock_llm.llm_chat.side_effect = fake_llm_chat

    context = {"user_memories": ["a", "b", "c"]}
    plan = await planner.plan("summarization", "msg", 1, 2, context=context)

    assert "prompt" in captured_prompt
    assert "User Context / Memory" in captured_prompt["prompt"]
    assert "direct" in captured_prompt["prompt"]
    assert "concise" in captured_prompt["prompt"]
    assert isinstance(plan, dict)
    assert isinstance(plan.get("steps"), list)


@pytest.mark.asyncio
async def test_workflow_planner_invalid_actions_sanitized(monkeypatch, mock_llm):
    from app.orchestrator.workflow_planning import WorkflowPlanner

    planner = WorkflowPlanner(mock_llm)

    def fake_llm_chat(prompt, system_prompt, response_format, temperature):
        return {"steps": [{"action": "retrieve_memory"}, {"action": "delete_meeting"}, {"action": "summarize"}]}

    mock_llm.llm_chat.side_effect = fake_llm_chat

    plan = await planner.plan("summarization", "msg", 1, 2, context=None)

    actions = [step["action"] for step in plan.get("steps", [])]
    assert actions[0] == "skip_step"
    assert actions[1] == "skip_step"
    assert actions[2] == "summarize"

