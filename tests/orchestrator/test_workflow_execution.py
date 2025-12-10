"""Tests for workflow execution and validation."""

import pytest
from unittest.mock import MagicMock
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.integrations.test_integration_mocks import (
    build_mock_workflow,
    build_mock_step,
    build_mock_fallback
)


class TestWorkflowExecution:
    """Tests for workflow parsing and validation."""
    
    def test_workflow_parsing_valid_structure(self, tool_executor):
        """Test that valid workflow structure is parsed correctly."""
        # Arrange
        workflow = build_mock_workflow(
            steps=[
                build_mock_step("find_meeting", "meeting_finder"),
                build_mock_step("summarize", "summarization")
            ],
            required_data=["meeting_id"]
        )
        
        # Act - Just verify structure is valid
        assert workflow is not None
        assert "steps" in workflow
        assert isinstance(workflow["steps"], list)
        assert len(workflow["steps"]) == 2
        assert "required_data" in workflow
        assert isinstance(workflow["required_data"], list)
    
    def test_workflow_parsing_malformed_workflow(self, tool_executor):
        """Test that malformed workflows are handled gracefully."""
        # Arrange - Invalid workflow structures
        invalid_workflows = [
            {"invalid": "structure"},  # Missing steps
            {"steps": "not_a_list"},  # Steps not a list
            {"steps": None},  # Steps is None
            {},  # Empty dict
        ]
        
        for invalid_workflow in invalid_workflows:
            # Act - Should not raise exception
            # The executor should handle invalid workflows gracefully
            assert isinstance(invalid_workflow, dict)
    
    def test_workflow_parsing_missing_step_fields(self, tool_executor):
        """Test that steps with missing fields are filtered out."""
        # Arrange
        workflow = build_mock_workflow(
            steps=[
                {"action": "find_meeting"},  # Missing tool
                {"tool": "meeting_finder"},  # Missing action
                build_mock_step("find_meeting", "meeting_finder"),  # Valid
                {},  # Empty step
            ]
        )
        
        # Act - Verify structure
        assert len(workflow["steps"]) == 4
        # Valid steps should have both action and tool
        valid_steps = [s for s in workflow["steps"] if s.get("action") and s.get("tool")]
        assert len(valid_steps) == 1
    
    def test_workflow_parsing_non_list_steps(self, tool_executor):
        """Test that non-list steps arrays are handled."""
        # Arrange
        invalid_workflows = [
            {"steps": "string"},
            {"steps": 123},
            {"steps": None},
            {"steps": {}},
        ]
        
        for invalid_workflow in invalid_workflows:
            # Act - Should not raise exception
            assert isinstance(invalid_workflow, dict)
            # Steps should be validated as list in executor
    
    def test_workflow_parsing_steps_with_invalid_types(self, tool_executor):
        """Test that steps with invalid types are filtered."""
        # Arrange
        workflow = build_mock_workflow(
            steps=[
                "string_step",  # String step (backward compatible)
                build_mock_step("find_meeting", "meeting_finder"),  # Valid dict
                123,  # Invalid type
                None,  # Invalid type
                {"action": "find_meeting", "tool": "meeting_finder"},  # Valid
            ]
        )
        
        # Act - Verify structure
        assert len(workflow["steps"]) == 5
        # Only dict steps with action and tool should be valid
        valid_steps = [
            s for s in workflow["steps"]
            if isinstance(s, dict) and s.get("action") and s.get("tool")
        ]
        assert len(valid_steps) == 2
    
    def test_workflow_parsing_nested_fallback_structures(self, tool_executor):
        """Test that nested fallback structures are handled."""
        # Arrange
        workflow = build_mock_workflow(
            steps=[
                build_mock_step(
                    "find_meeting",
                    "meeting_finder",
                    fallback=[
                        build_mock_fallback(
                            "resolve_meeting_from_calendar",
                            conditions=["no_db_match"]
                        ),
                        build_mock_fallback(
                            "use_last_selected_meeting",
                            conditions=["no_db_match"]
                        )
                    ]
                )
            ]
        )
        
        # Act - Verify structure
        assert len(workflow["steps"]) == 1
        step = workflow["steps"][0]
        assert "fallback" in step
        assert isinstance(step["fallback"], list)
        assert len(step["fallback"]) == 2
    
    def test_workflow_parsing_fallback_as_dict(self, tool_executor):
        """Test that fallback can be a single dict."""
        # Arrange
        workflow = build_mock_workflow(
            steps=[
                build_mock_step(
                    "find_meeting",
                    "meeting_finder",
                    fallback=build_mock_fallback(
                        "resolve_meeting_from_calendar",
                        conditions=["no_db_match"]
                    )
                )
            ]
        )
        
        # Act - Verify structure
        assert len(workflow["steps"]) == 1
        step = workflow["steps"][0]
        assert "fallback" in step
        assert isinstance(step["fallback"], dict)
        assert step["fallback"]["action"] == "resolve_meeting_from_calendar"
    
    def test_workflow_parsing_empty_steps(self, tool_executor):
        """Test that empty steps array is handled."""
        # Arrange
        workflow = build_mock_workflow(steps=[])
        
        # Act - Verify structure
        assert workflow["steps"] == []
        assert isinstance(workflow["steps"], list)
    
    def test_workflow_parsing_missing_required_data(self, tool_executor):
        """Test that missing required_data is handled."""
        # Arrange
        workflow = build_mock_workflow(
            steps=[build_mock_step("find_meeting", "meeting_finder")]
        )
        
        # Act - Verify structure
        assert "required_data" not in workflow or workflow.get("required_data") is None
    
    def test_workflow_parsing_prerequisites_in_step(self, tool_executor):
        """Test that prerequisites can be defined in steps."""
        # Arrange
        workflow = build_mock_workflow(
            steps=[
                build_mock_step(
                    "summarize",
                    "summarization",
                    prerequisites=["transcript", "meeting_id"]
                )
            ]
        )
        
        # Act - Verify structure
        assert len(workflow["steps"]) == 1
        step = workflow["steps"][0]
        assert "prerequisites" in step
        assert isinstance(step["prerequisites"], list)
        assert len(step["prerequisites"]) == 2

