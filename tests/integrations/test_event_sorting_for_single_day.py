"""
Integration-layer test for GoogleCalendarClient.get_events_on_date (isolated).
Ensures:
- exact 24h window with maxResults=50, singleEvents=True, orderBy='startTime'
- only target-year events returned
- sorting newest → oldest
"""

import sys
import types
from datetime import date as _dt_date

# --- Stub Google modules to avoid external deps during import ---
stub_googleapiclient = types.ModuleType("googleapiclient")
stub_googleapiclient.discovery = types.ModuleType("googleapiclient.discovery")
stub_googleapiclient.discovery.build = lambda *a, **k: None
sys.modules["googleapiclient"] = stub_googleapiclient
sys.modules["googleapiclient.discovery"] = stub_googleapiclient.discovery

stub_google_pkg = types.ModuleType("google")
stub_google_auth = types.ModuleType("google.auth")
stub_google_auth.transport = types.ModuleType("google.auth.transport")
stub_google_auth.transport.requests = types.ModuleType("google.auth.transport.requests")
stub_google_auth.credentials = types.ModuleType("google.auth.credentials")
stub_google_auth.transport.requests.Request = type("Request", (), {})
stub_google_auth.external_account_authorized_user = lambda *args, **kwargs: None
stub_google_oauth2 = types.ModuleType("google.oauth2")
stub_google_oauth2.service_account = types.ModuleType("google.oauth2.service_account")
stub_google_oauth2.credentials = types.ModuleType("google.oauth2.credentials")
stub_google_oauth2.credentials.Credentials = type("Credentials", (), {})

stub_google_auth_oauthlib = types.ModuleType("google_auth_oauthlib")
stub_google_auth_oauthlib.flow = types.ModuleType("google_auth_oauthlib.flow")
stub_google_auth_oauthlib.helpers = types.ModuleType("google_auth_oauthlib.helpers")
stub_google_auth_oauthlib.flow.InstalledAppFlow = type(
    "InstalledAppFlow",
    (),
    {
        "from_client_secrets_file": classmethod(lambda cls, *a, **k: cls()),
        "run_local_server": lambda self, *a, **k: None,
    },
)

dummy_settings = types.SimpleNamespace(
    google_client_secret_file="client_secret.json",
    google_token_file="token.json",
    google_scopes="https://www.googleapis.com/auth/calendar.readonly",
    google_client_id="dummy",
    google_client_secret="dummy",
)
stub_app_config = types.ModuleType("app.config")
stub_app_config.settings = dummy_settings
sys.modules["app.config"] = stub_app_config

sys.modules["google"] = stub_google_pkg
sys.modules["google.auth"] = stub_google_auth
sys.modules["google.auth.transport"] = stub_google_auth.transport
sys.modules["google.auth.transport.requests"] = stub_google_auth.transport.requests
sys.modules["google.auth.credentials"] = stub_google_auth.credentials
sys.modules["google.oauth2"] = stub_google_oauth2
sys.modules["google.oauth2.service_account"] = stub_google_oauth2.service_account
sys.modules["google.oauth2.credentials"] = stub_google_oauth2.credentials
sys.modules["google_auth_oauthlib"] = stub_google_auth_oauthlib
sys.modules["google_auth_oauthlib.flow"] = stub_google_auth_oauthlib.flow
sys.modules["google_auth_oauthlib.helpers"] = stub_google_auth_oauthlib.helpers

from app.integrations.google_calendar_client import GoogleCalendarClient
from app.utils.date_utils import extract_event_datetime


class MockEventsList:
    def __init__(self, pages):
        self.pages = pages
        self.call_count = 0
        self.captured_params = []

    def list(self, **kwargs):
        self.captured_params.append(kwargs.copy())
        return self

    def execute(self):
        page = self.pages[self.call_count]
        self.call_count += 1
        return page


class MockService:
    def __init__(self, pages):
        self.events_list = MockEventsList(pages)

    def events(self):
        return self.events_list


def make_event(event_id, summary, iso_datetime):
    return {
        "id": event_id,
        "summary": summary,
        "start": {"dateTime": iso_datetime},
        "end": {"dateTime": iso_datetime},
    }


def test_get_events_on_date_filters_year_and_sorts_newest_first():
    target_date = _dt_date(2025, 10, 29)

    page1_events = [
        make_event("evt-2024", "Old 2024 event", "2024-10-29T09:00:00Z"),
        make_event("evt-2025-1", "2025 morning", "2025-10-29T09:00:00Z"),
    ]
    page2_events = [
        make_event("evt-2025-2", "2025 evening", "2025-10-29T18:00:00Z"),
    ]

    pages = [
        {"items": page1_events, "nextPageToken": "token-2"},
        {"items": page2_events, "nextPageToken": None},
    ]

    mock_service = MockService(pages)
    client = object.__new__(GoogleCalendarClient)
    client.service = mock_service

    events = client.get_events_on_date(target_date)

    # Assert query params
    assert mock_service.events_list.captured_params, "No requests captured"
    params = mock_service.events_list.captured_params[0]
    assert params["timeMin"].startswith("2025-10-29T00:00:00")
    assert params["timeMax"].startswith("2025-10-29T23:59:59")
    assert params["maxResults"] == 50
    assert params["singleEvents"] is True
    assert params["orderBy"] == "startTime"

    # Only 2025 events should remain
    assert len(events) == 2
    years = [extract_event_datetime(e).year for e in events]
    assert all(y == 2025 for y in years)

    # Sorted newest -> oldest
    times = [extract_event_datetime(e) for e in events]
    assert times == sorted(times, reverse=True)

