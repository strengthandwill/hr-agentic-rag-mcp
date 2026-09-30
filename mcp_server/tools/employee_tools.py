"""Mock-structured-data MCP tools: lookup_employee_profile, check_pto_balance, lookup_benefits_status."""
from __future__ import annotations

from mcp_server import data_access


def lookup_employee_profile(employee_id: str) -> dict:
    """Look up a CPDA employee's profile (role, department, employment type, manager, location)."""
    emp = data_access.get_employee(employee_id)
    if emp is None:
        return {
            "found": False,
            "employee_id": employee_id,
            "message": f"No employee found with ID '{employee_id}'. Ask the user to confirm their employee ID.",
        }
    return {"found": True, **emp}


def check_pto_balance(employee_id: str) -> dict:
    """Check a CPDA employee's Annual Leave (PTO) and related leave balances."""
    emp = data_access.get_employee(employee_id)
    if emp is None:
        return {
            "found": False,
            "employee_id": employee_id,
            "message": f"No employee found with ID '{employee_id}'. Ask the user to confirm their employee ID.",
        }
    balance = data_access.get_pto_balance(employee_id)
    if balance is None:
        return {
            "found": False,
            "employee_id": employee_id,
            "message": "Employee exists but has no PTO balance record.",
        }
    return {
        "found": True,
        "employee_id": employee_id,
        "employment_type": emp["employment_type"],
        "as_of_date": data_access.PTO_AS_OF_DATE,
        **balance,
    }


def lookup_benefits_status(employee_id: str) -> dict:
    """Check a CPDA employee's benefits elections (medical, dental, wellness, dependents)."""
    emp = data_access.get_employee(employee_id)
    if emp is None:
        return {
            "found": False,
            "employee_id": employee_id,
            "message": f"No employee found with ID '{employee_id}'. Ask the user to confirm their employee ID.",
        }
    benefits = data_access.get_benefits_election(employee_id)
    if benefits is None:
        return {
            "found": False,
            "employee_id": employee_id,
            "message": "Employee exists but has no benefits election record.",
        }
    return {
        "found": True,
        "employee_id": employee_id,
        "employment_type": emp["employment_type"],
        "employment_status": emp.get("employment_status"),
        **benefits,
    }
