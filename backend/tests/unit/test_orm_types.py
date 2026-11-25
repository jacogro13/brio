import pytest
from sqlalchemy.dialects import postgresql

from chatbot.adapters.persistence.postgres.orm import ToolEventList
from chatbot.domain.conversation.model import ToolEvent, ToolResult

DIALECT = postgresql.dialect()


def test_tool_events_round_trip_through_the_column_type():
    column_type = ToolEventList()
    events = [
        ToolEvent(
            id=1,
            tool="web_search",
            query="pi",
            ok=True,
            summary="2 results",
            results=[ToolResult(title="Pi", url="https://example.org/pi")],
        ),
        ToolEvent(id=2, tool="fetch_page", url="https://example.org/pi"),
    ]

    stored = column_type.process_bind_param(events, DIALECT)
    loaded = column_type.process_result_value(stored, DIALECT)

    assert stored == [event.to_json() for event in events]
    assert loaded == events


@pytest.mark.parametrize("direction", ["bind", "result"])
def test_null_tool_events_stay_null(direction: str):
    column_type = ToolEventList()

    if direction == "bind":
        value = column_type.process_bind_param(None, DIALECT)
    else:
        value = column_type.process_result_value(None, DIALECT)

    assert value is None
