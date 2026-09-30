"""Loads mock structured HR data (employees, PTO, benefits, tickets) into memory.

Ticket creation is an in-memory mutation on top of the committed `tickets_seed.json` file, so
the mock ticket store resets to the seed data on every process restart -- appropriate for a
free-tier deployment with no paid database, and explicitly a *mock* action per the assignment's
safety requirements.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from app.config import MOCK_DATA_DIR


def _load_json(filename: str) -> dict:
    path = Path(MOCK_DATA_DIR) / filename
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


_employees_raw = _load_json("employees.json")
_pto_raw = _load_json("pto_balances.json")
_benefits_raw = _load_json("benefits_elections.json")
_tickets_raw = _load_json("tickets_seed.json")

EMPLOYEES: dict[str, dict] = {e["employee_id"]: e for e in _employees_raw["employees"]}
PTO_BALANCES: dict[str, dict] = _pto_raw["balances"]
PTO_AS_OF_DATE: str = _pto_raw["as_of_date"]
BENEFITS_ELECTIONS: dict[str, dict] = _benefits_raw["elections"]

_lock = threading.Lock()
_tickets: list[dict] = list(_tickets_raw["tickets"])
_next_ticket_number: int = _tickets_raw["next_ticket_number"]


def get_employee(employee_id: str) -> dict | None:
    return EMPLOYEES.get(employee_id)


def get_pto_balance(employee_id: str) -> dict | None:
    return PTO_BALANCES.get(employee_id)


def get_benefits_election(employee_id: str) -> dict | None:
    return BENEFITS_ELECTIONS.get(employee_id)


def list_tickets_for_employee(employee_id: str) -> list[dict]:
    return [t for t in _tickets if t["employee_id"] == employee_id]


def create_ticket(employee_id: str, category: str, summary: str) -> dict:
    global _next_ticket_number
    with _lock:
        ticket = {
            "ticket_id": f"TCK-{_next_ticket_number}",
            "employee_id": employee_id,
            "category": category,
            "summary": summary,
            "status": "open",
            "created_at": datetime.now(timezone.utc).astimezone().isoformat(),
            "resolved_at": None,
        }
        _tickets.append(ticket)
        _next_ticket_number += 1
    return ticket


def all_tickets() -> list[dict]:
    return list(_tickets)
