from __future__ import annotations

from datetime import date, time
from pathlib import Path
import sys

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend import models  # noqa: F401
from backend.database.base import Base
from backend.models.address import Address
from backend.models.availability import Availability
from backend.models.professional import Professional
from backend.models.professional_service import ProfessionalService
from backend.models.service import Service
from backend.models.user import User
from backend.services import availability_service
from backend.services import booking_service
from ai_engine.graph.builder import build_graph


class Trace:
    def __init__(self) -> None:
        self.events: list[str] = []


@pytest.fixture()
def booking_graph_environment(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = SessionLocal()

    user = User(
        name="AI Booking E2E User",
        email="ai-booking-e2e@example.com",
        phone="9999999997",
        password_hash="test-only",
    )
    db.add(user)
    db.flush()

    address = Address(
        user_id=user.id,
        address="25 Test Road",
        city="Jaipur",
        state="Rajasthan",
        postal_code="302001",
    )
    service = Service(
        name="AC Repair",
        description="Air conditioner repair",
        category="Home Services",
        base_price=499.0,
        duration_minutes=60,
        is_active=True,
    )
    professional = Professional(
        name="E2E Technician",
        specialization="AC Repair",
        rating=4.9,
        is_active=True,
    )
    db.add_all([address, service, professional])
    db.flush()

    db.add(
        ProfessionalService(
            professional_id=professional.id,
            service_id=service.id,
        )
    )
    db.add(
        Availability(
            professional_id=professional.id,
            service_id=service.id,
            date=date(2026, 9, 16),
            start_time=time(16, 0),
            end_time=time(17, 0),
            is_available=True,
        )
    )
    db.commit()

    trace = Trace()

    # The graph builder itself remains unchanged.  For this deterministic E2E
    # test we inject lightweight workflow nodes so the test validates graph
    # orchestration and the real backend service boundary without requiring a
    # live Groq/LLM call.
    import ai_engine.graph.builder as builder

    def fake_context(state):
        trace.events.append("context")
        return state

    def fake_intent(state):
        trace.events.append("intent")
        return {"intent": "service_booking"}

    def fake_entity(state):
        trace.events.append("entity")
        return {
            "service_id": service.id,
            "service_name": service.name,
            "booking_date": "2026-09-16",
            "booking_start_time": "16:00",
            "booking_end_time": "17:00",
            "address_id": address.id,
            "professional_id": None,
            "missing_fields": [],
            "awaiting_user_input": False,
        }

    def fake_followup(state):
        trace.events.append("followup")
        return {"awaiting_user_input": False}

    def fake_planner(state):
        trace.events.append("planner")
        return {
            "planner": {
                "action": "CHECK_AVAILABILITY",
                "tool": "check_availability",
                "arguments": {
                    "service_id": service.id,
                    "requested_date": "2026-09-16",
                    "start_time": "16:00",
                    "end_time": "17:00",
                },
            },
            "planner_args": {
                "service_id": service.id,
                "requested_date": "2026-09-16",
                "start_time": "16:00",
                "end_time": "17:00",
            },
        }

    def fake_policy(state):
        trace.events.append("policy")
        return {
            "policy_result": {
                "allowed": True,
                "action": "CHECK_AVAILABILITY",
                "tool": "check_availability",
            }
        }

    def fake_decision(state):
        trace.events.append("decision")
        return {
            "decision": {
                "action": "CHECK_AVAILABILITY",
                "tool": "check_availability",
            },
            "action": "CHECK_AVAILABILITY",
            "tool_name": "check_availability",
            "decision_route": "tool",
        }

    def fake_tool(state, runtime_db):
        trace.events.append("tool")
        available = availability_service.check_availability(
            db=runtime_db,
            service_id=service.id,
            requested_date=date(2026, 9, 16),
            start_time=time(16, 0),
            end_time=time(17, 0),
            professional_id=None,
        )
        trace.events.append("availability")
        professionals = availability_service.get_available_professionals(
            db=runtime_db,
            service_id=service.id,
            requested_date=date(2026, 9, 16),
            start_time=time(16, 0),
            end_time=time(17, 0),
        )
        assert available is True
        assert professionals
        selected = professionals[0]
        trace.events.append("professional_selection")

        final_available = availability_service.check_availability(
            db=runtime_db,
            service_id=service.id,
            requested_date=date(2026, 9, 16),
            start_time=time(16, 0),
            end_time=time(17, 0),
            professional_id=selected.id,
        )
        trace.events.append("final_availability")
        assert final_available is True

        booking = booking_service.create_booking(
            db=runtime_db,
            user_id=user.id,
            service_id=service.id,
            professional_id=selected.id,
            address_id=address.id,
            requested_date=date(2026, 9, 16),
            start_time=time(16, 0),
            end_time=time(17, 0),
        )
        trace.events.append("booking")
        return {
            "tool_name": "create_booking",
            "tool_result": {
                "success": True,
                "booking_id": booking.id,
            },
            "booking_id": booking.id,
            "booking_status": booking.status,
            "professional_id": selected.id,
            "professional_name": selected.name,
        }

    def fake_response(state):
        trace.events.append("response")
        return state

    monkeypatch.setattr(builder, "context_node", fake_context)
    monkeypatch.setattr(builder, "intent_node", fake_intent)
    monkeypatch.setattr(builder, "entity_node", fake_entity)
    monkeypatch.setattr(builder, "followup_node", fake_followup)
    monkeypatch.setattr(builder, "planner_node", fake_planner)
    monkeypatch.setattr(builder, "policy_node", fake_policy)
    monkeypatch.setattr(builder, "decision_node", fake_decision)
    monkeypatch.setattr(builder, "tool_node", fake_tool)
    monkeypatch.setattr(builder, "response_node", fake_response)

    graph = build_graph(db=db)

    try:
        yield {
            "db": db,
            "graph": graph,
            "trace": trace,
            "user": user,
        }
    finally:
        db.close()
        engine.dispose()


def test_booking_e2e_calls_backend_availability_before_booking(
    booking_graph_environment,
):
    data = booking_graph_environment

    result = data["graph"].invoke(
        {
            "db": data["db"],
            "user_id": data["user"].id,
            "message": "I need an AC repair tomorrow at 4 PM",
        }
    )

    trace = data["trace"].events

    assert "intent" in trace
    assert "entity" in trace
    assert "planner" in trace
    assert "policy" in trace
    assert "decision" in trace
    assert "availability" in trace
    assert "professional_selection" in trace
    assert "final_availability" in trace
    assert "booking" in trace
    assert "response" in trace

    assert trace.index("availability") < trace.index("booking")
    assert trace.index("final_availability") < trace.index("booking")
    assert result["booking_id"] is not None
    assert result["booking_status"] == "confirmed"
