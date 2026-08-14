import pytest
from pydantic import ValidationError

from agenttakt.bridge import protocol


def sample_plan():
    return {
        "graph_id": "g",
        "nodes": [{"id": "a", "type": "t", "title": "A"}],
        "edges": [],
    }


def test_round_trip_review_request():
    request = protocol.ReviewRequest(request_id="r1", plan=sample_plan())
    line = protocol.encode(request)
    assert line.endswith(b"\n")
    assert line.count(b"\n") == 1  # NDJSON: 1 行 1 メッセージ
    decoded = protocol.decode(line)
    assert isinstance(decoded, protocol.ReviewRequest)
    assert decoded.request_id == "r1"
    assert decoded.plan.nodes[0].id == "a"


def test_discriminator_selects_message_type():
    response = protocol.ReviewResponse(
        request_id="r1", decision="approved", plan=sample_plan()
    )
    assert isinstance(protocol.decode(protocol.encode(response)), protocol.ReviewResponse)

    error = protocol.ErrorMessage(code="invalid_message", message="boom")
    assert isinstance(protocol.decode(protocol.encode(error)), protocol.ErrorMessage)


def test_round_trip_show_plan_and_ack():
    request = protocol.ShowPlanRequest(request_id="s1", plan=sample_plan())
    decoded = protocol.decode(protocol.encode(request))
    assert isinstance(decoded, protocol.ShowPlanRequest)
    assert decoded.request_id == "s1"

    ack = protocol.Ack(request_id="s1")
    decoded_ack = protocol.decode(protocol.encode(ack))
    assert isinstance(decoded_ack, protocol.Ack)
    assert decoded_ack.request_id == "s1"


def test_unknown_type_raises():
    with pytest.raises(ValidationError):
        protocol.decode(b'{"type": "unknown"}')


def test_extra_plan_fields_survive_round_trip():
    plan = sample_plan() | {"executor_meta": {"session": "xyz"}}
    request = protocol.ReviewRequest(request_id="r1", plan=plan)
    decoded = protocol.decode(protocol.encode(request))
    assert decoded.plan.model_dump()["executor_meta"] == {"session": "xyz"}
