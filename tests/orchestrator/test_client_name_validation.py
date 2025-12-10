"""
Test script for Gap C3 client_name validation in _prepare_summarization_data().

This script tests client_name validation without modifying production code.
"""

import sys
import asyncio
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from unittest.mock import Mock, MagicMock, patch, AsyncMock
from typing import Dict, Any, Optional

# Mock classes
class MockClient:
    def __init__(self, client_id: int, name: str = "Test Client"):
        self.id = client_id
        self.name = name

class MockMemoryRepository:
    def __init__(self):
        self.clients = {
            5: MockClient(5, "MTCA"),
            10: MockClient(10, "Good Health"),
            15: MockClient(15, "Acme Corp")
        }
    
    def search_clients_by_name(self, name: str, user_id: Optional[int] = None):
        """Return clients matching name (case-insensitive partial match)."""
        name_lower = name.lower().strip()
        results = []
        for client in self.clients.values():
            if name_lower in client.name.lower():
                results.append(client)
        return results
    
    def get_client_by_id(self, client_id: int):
        """Return client if exists, None otherwise."""
        return self.clients.get(client_id)
    
    def get_meeting_by_id(self, meeting_id: int):
        return None

async def test_case(name: str, client_name: Any, client_id: Optional[int], 
                    mock_search_results: Optional[list] = None,
                    expected_error: Optional[Dict[str, str]] = None):
    """Run a single test case."""
    print(f"\n{'='*70}")
    print(f"TEST: {name}")
    print(f"{'='*70}")
    
    # Setup mocks
    mock_db = MagicMock()
    mock_memory = MockMemoryRepository()
    
    # Prepare test data
    prepared_data = {
        "client_name": client_name,
        "meeting_id": None,
        "calendar_event_id": None,
        "target_date": None
    }
    
    # Override search_clients_by_name if custom results provided
    if mock_search_results is not None:
        mock_memory.search_clients_by_name = Mock(return_value=mock_search_results)
    
    # Import ToolExecutor
    from app.orchestrator.tool_execution import ToolExecutor
    
    # Create ToolExecutor instance with mocked dependencies
    with patch('app.orchestrator.tool_execution.SummarizationTool'):
        with patch('app.orchestrator.tool_execution.MeetingBriefTool'):
            with patch('app.orchestrator.tool_execution.FollowUpTool'):
                with patch('app.orchestrator.tool_execution.IntegrationDataFetcher') as mock_fetcher:
                    # Mock integration_data_fetcher to avoid real API calls
                    mock_fetcher_instance = MagicMock()
                    mock_fetcher_instance.process_calendar_event_for_summarization = AsyncMock(return_value={
                        "meeting_id": None,
                        "transcript": None,
                        "meeting_title": "Test",
                        "has_transcript": False
                    })
                    mock_fetcher.return_value = mock_fetcher_instance
                    
                    with patch('app.orchestrator.tool_execution.MeetingFinder') as mock_finder:
                        mock_finder_instance = MagicMock()
                        mock_finder_instance.find_meeting_in_database = Mock(return_value=None)
                        mock_finder_instance.find_meeting_in_calendar = Mock(return_value=(None, None))
                        mock_finder.return_value = mock_finder_instance
                        
                        executor = ToolExecutor(
                            db=mock_db,
                            memory=mock_memory,
                            summarization_tool=MagicMock(),
                            meeting_brief_tool=MagicMock(),
                            followup_tool=MagicMock(),
                            integration_data_fetcher=mock_fetcher_instance
                        )
                        
                        try:
                            # Call the method
                            result = await executor._prepare_summarization_data(
                                prepared_data=prepared_data,
                                user_id=1,
                                client_id=client_id
                            )
                            
                            # Verify results
                            print(f"\nINPUT:")
                            print(f"  client_name: {client_name} (type: {type(client_name).__name__})")
                            print(f"  client_id: {client_id}")
                            print(f"\nOUTPUT:")
                            print(f"  result keys: {list(result.keys())}")
                            
                            # Check for errors
                            if "error" in result:
                                print(f"  result['error']: {result.get('error')}")
                                print(f"  result['tool_name']: {result.get('tool_name')}")
                                
                                # Validate error format
                                if expected_error:
                                    if result.get("tool_name") != expected_error.get("tool_name"):
                                        print(f"  ❌ FAILED: tool_name mismatch")
                                        print(f"  Expected: {expected_error.get('tool_name')}")
                                        print(f"  Actual: {result.get('tool_name')}")
                                        return False
                                    
                                    if result.get("error") != expected_error.get("error"):
                                        print(f"  ❌ FAILED: error message mismatch")
                                        print(f"  Expected: {expected_error.get('error')}")
                                        print(f"  Actual: {result.get('error')}")
                                        return False
                                    
                                    print(f"  ✅ PASSED: Error format and message correct")
                                    return True
                                else:
                                    print(f"  ❌ FAILED: Unexpected error returned")
                                    print(f"  Expected: No error (success path)")
                                    print(f"  Actual: {result.get('error')}")
                                    return False
                            
                            # If no error, validation passed
                            if expected_error is None:
                                print(f"  ✅ PASSED: No error returned, validation passed")
                                return True
                            else:
                                print(f"  ❌ FAILED: Expected error but none returned")
                                return False
                                
                        except Exception as e:
                            print(f"  ❌ EXCEPTION: {type(e).__name__}: {e}")
                            import traceback
                            traceback.print_exc()
                            return False

async def main():
    """Run all test cases."""
    print("="*70)
    print("GAP C3 CLIENT_NAME VALIDATION TESTS")
    print("="*70)
    print("Testing _prepare_summarization_data() client_name validation")
    
    results = []
    
    # Test 1: Rejects non-string client_name
    results.append(await test_case(
        "1 - client_name=123 (non-string, should fail)",
        client_name=123,
        client_id=None,
        expected_error={
            "tool_name": "summarization",
            "error": "Client name must be a string"
        }
    ))
    
    # Test 2: Rejects empty string client_name
    results.append(await test_case(
        "2 - client_name='' (empty string, should fail)",
        client_name="",
        client_id=None,
        expected_error={
            "tool_name": "summarization",
            "error": "Client '' does not exist in database"
        }
    ))
    
    # Test 3: Rejects whitespace-only client_name
    results.append(await test_case(
        "3 - client_name='   ' (whitespace-only, should fail)",
        client_name="   ",
        client_id=None,
        expected_error={
            "tool_name": "summarization",
            "error": "Client '' does not exist in database"
        }
    ))
    
    # Test 4: Rejects valid-looking client_name that does NOT exist in DB
    results.append(await test_case(
        "4 - client_name='NonExistent Client' (not in DB, should fail)",
        client_name="NonExistent Client",
        client_id=None,
        mock_search_results=[],  # Empty list = no match
        expected_error={
            "tool_name": "summarization",
            "error": "Client 'NonExistent Client' does not exist in database"
        }
    ))
    
    # Test 5: Accepts valid client_name that DOES exist
    results.append(await test_case(
        "5 - client_name='MTCA' (exists in DB, should pass)",
        client_name="MTCA",
        client_id=None,
        mock_search_results=[MockClient(5, "MTCA")],  # Exact match
        expected_error=None
    ))
    
    # Test 6: Accepts valid client_name with different case
    results.append(await test_case(
        "6 - client_name='mtca' (lowercase, exists in DB, should pass)",
        client_name="mtca",
        client_id=None,
        mock_search_results=[MockClient(5, "MTCA")],  # Case-insensitive match
        expected_error=None
    ))
    
    # Test 7: Rejects mismatch between client_name and client_id
    results.append(await test_case(
        "7 - client_name='MTCA' (id=5), client_id=10 (mismatch, should fail)",
        client_name="MTCA",
        client_id=10,
        mock_search_results=[MockClient(5, "MTCA")],  # client_name matches id=5
        expected_error={
            "tool_name": "summarization",
            "error": "Client name and client_id refer to different clients"
        }
    ))
    
    # Test 8: Accepts consistent client_name and client_id
    results.append(await test_case(
        "8 - client_name='MTCA' (id=5), client_id=5 (consistent, should pass)",
        client_name="MTCA",
        client_id=5,
        mock_search_results=[MockClient(5, "MTCA")],  # Both refer to same client
        expected_error=None
    ))
    
    # Test 9: Accepts client_name with whitespace that matches after strip
    results.append(await test_case(
        "9 - client_name='  MTCA  ' (with whitespace, should strip and pass)",
        client_name="  MTCA  ",
        client_id=None,
        mock_search_results=[MockClient(5, "MTCA")],  # Should match after strip
        expected_error=None
    ))
    
    # Test 10: Rejects client_id that is non-int when both provided
    results.append(await test_case(
        "10 - client_name='MTCA' (valid), client_id='abc' (non-int, should fail)",
        client_name="MTCA",
        client_id="abc",
        mock_search_results=[MockClient(5, "MTCA")],
        expected_error={
            "tool_name": "summarization",
            "error": "Invalid client_id format"
        }
    ))
    
    # ===== Summary =====
    print(f"\n{'='*70}")
    print("TEST SUMMARY")
    print(f"{'='*70}")
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    print(f"Failed: {total - passed}/{total}")
    
    if passed == total:
        print("\n✅ ALL TESTS PASSED")
    else:
        print("\n❌ SOME TESTS FAILED")
    
    print(f"\n{'='*70}")
    print("VALIDATION BRANCHES VERIFIED:")
    print(f"{'='*70}")
    print("1. Non-string client_name rejection")
    print("2. Empty/whitespace-only client_name rejection")
    print("3. Non-existent client_name rejection")
    print("4. Valid client_name acceptance")
    print("5. client_name and client_id consistency validation")
    print("6. Case-insensitive matching")
    print("7. Whitespace normalization")

if __name__ == "__main__":
    asyncio.run(main())

