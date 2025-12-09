import datetime
import sys
import types

# Stub the calendar client module to avoid external dependencies during tests
dummy_gc = types.ModuleType("app.integrations.google_calendar_client")


def _noop(*args, **kwargs):
    return None


def _empty_list(*args, **kwargs):
    return []


def _is_event_in_past_stub(event, now):
    return True


dummy_gc.get_calendar_event_by_id = _noop
dummy_gc.get_calendar_events_on_date = _empty_list
dummy_gc.get_calendar_events_by_time_range = _empty_list
dummy_gc.search_calendar_events_by_keyword = _empty_list
dummy_gc._is_event_in_past = _is_event_in_past_stub

sys.modules["app.integrations.google_calendar_client"] = dummy_gc

from app.orchestrator.meeting_finder import MeetingFinder


class StubMeeting:
    def __init__(self, meeting_id, title, scheduled_time):
        self.id = meeting_id
        self.title = title
        self.scheduled_time = scheduled_time
        self.summary = ""
        self.transcript = None
        self.attendees = []


class StubClient:
    def __init__(self, client_id, name):
        self.id = client_id
        self.name = name


class StubMemoryRepo:
    def __init__(self, clients=None, meetings_by_client=None, meetings_by_user=None):
        self.clients = clients or []
        self.meetings_by_client = meetings_by_client or {}
        self.meetings_by_user = meetings_by_user or {}

    def get_meeting_by_id(self, meeting_id):
        for meetings in list(self.meetings_by_client.values()) + list(self.meetings_by_user.values()):
            for m in meetings:
                if m.id == meeting_id:
                    return m
        return None

    def search_clients_by_name(self, name, user_id=None):
        return [c for c in self.clients if c.name.lower() == name.lower()]

    def get_meetings_by_client(self, client_id, limit=None):
        meetings = self.meetings_by_client.get(client_id, [])
        return meetings[:limit] if limit else meetings

    def get_meetings_by_user(self, user_id, limit=None):
        meetings = self.meetings_by_user.get(user_id, [])
        return meetings[:limit] if limit else meetings


def make_dt(year, month, day):
    return datetime.datetime(year, month, day, 10, 0, 0, tzinfo=datetime.timezone.utc)


def test_client_date_no_match_returns_none():
    # MTCA client exists but no meetings on target date
    client = StubClient(1, "MTCA")
    memory = StubMemoryRepo(
        clients=[client],
        meetings_by_client={1: [StubMeeting(10, "MTCA Past", make_dt(2024, 10, 15))]},
    )
    finder = MeetingFinder(db=None, memory=memory)
    target_date = make_dt(2024, 10, 29)

    result = finder.find_meeting_in_database(
        client_name="MTCA",
        user_id=123,
        target_date=target_date,
    )

    assert result is None


def test_client_date_exact_match_returns_meeting():
    client = StubClient(1, "MTCA")
    mtca_meeting = StubMeeting(20, "MTCA Oct 29", make_dt(2024, 10, 29))
    memory = StubMemoryRepo(
        clients=[client],
        meetings_by_client={1: [mtca_meeting]},
    )
    finder = MeetingFinder(db=None, memory=memory)
    target_date = make_dt(2024, 10, 29)

    result = finder.find_meeting_in_database(
        client_name="MTCA",
        user_id=123,
        target_date=target_date,
    )

    assert result == mtca_meeting.id


def test_client_without_date_returns_most_recent():
    client = StubClient(1, "MTCA")
    old_meeting = StubMeeting(30, "MTCA Old", make_dt(2024, 9, 1))
    recent_meeting = StubMeeting(31, "MTCA Recent", make_dt(2024, 10, 1))
    memory = StubMemoryRepo(
        clients=[client],
        meetings_by_client={1: [old_meeting, recent_meeting]},
    )
    finder = MeetingFinder(db=None, memory=memory)

    result = finder.find_meeting_in_database(
        client_name="MTCA",
        user_id=123,
        target_date=None,
    )

    assert result == recent_meeting.id


def test_user_fallback_only_when_no_client():
    user_meeting = StubMeeting(40, "User Recent", make_dt(2024, 10, 5))
    memory = StubMemoryRepo(
        clients=[],
        meetings_by_user={123: [user_meeting]},
    )
    finder = MeetingFinder(db=None, memory=memory)

    result = finder.find_meeting_in_database(
        client_name=None,
        user_id=123,
        target_date=None,
    )

    assert result == user_meeting.id

