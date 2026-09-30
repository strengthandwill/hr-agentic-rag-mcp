"""Mock action MCP tools: create_mock_hr_ticket, draft_hr_email.

Both tools are safety-gated per the assignment's "prevent irreversible actions" requirement:
- create_mock_hr_ticket only writes to the in-memory mock ticket store, and only if the caller
  passes confirmed=True, which the agent's system prompt instructs it to set only after the user
  has explicitly agreed in the conversation. Passing confirmed=False (or omitting it) is a safe
  no-op preview.
- draft_hr_email never sends anything (no SMTP/API call exists in this codebase); it always
  returns a draft for the user to review, which is why it does not require a confirmation flag.
"""
from __future__ import annotations

from mcp_server import data_access

VALID_TICKET_CATEGORIES = {
    "pto",
    "benefits",
    "expense",
    "equipment",
    "remote_work",
    "conduct",
    "other",
}


def create_mock_hr_ticket(
    employee_id: str,
    category: str,
    summary: str,
    confirmed: bool = False,
) -> dict:
    """Create a mock HR ticket for human follow-up. Irreversible-action guardrail: only creates
    the ticket when confirmed=True; otherwise returns a preview without writing anything."""
    emp = data_access.get_employee(employee_id)
    if emp is None:
        return {
            "status": "error",
            "reason": "employee_not_found",
            "message": f"No employee found with ID '{employee_id}'.",
        }

    category_norm = category.lower().strip().replace(" ", "_")
    if category_norm not in VALID_TICKET_CATEGORIES:
        category_norm = "other"

    if not confirmed:
        return {
            "status": "preview_only",
            "message": (
                "Ticket NOT created. This is a preview -- ask the user to explicitly confirm, "
                "then call this tool again with confirmed=true."
            ),
            "preview": {
                "employee_id": employee_id,
                "category": category_norm,
                "summary": summary,
            },
        }

    ticket = data_access.create_ticket(employee_id, category_norm, summary)
    return {"status": "created", "ticket": ticket}


def draft_hr_email(to: str, subject: str, context: str, employee_id: str | None = None) -> dict:
    """Draft (but never send) an HR-related email. Always a mock draft for user review."""
    sender_name = "CPDA People & Culture Assistant"
    employee_name = None
    if employee_id:
        emp = data_access.get_employee(employee_id)
        if emp:
            employee_name = emp["name"]

    greeting = f"Hi {to.split('@')[0] if '@' in to else to},"
    signature_name = employee_name or "CPDA Employee"
    body = (
        f"{greeting}\n\n"
        f"{context.strip()}\n\n"
        f"Best regards,\n{signature_name}\n"
        f"(Drafted with assistance from the {sender_name} -- not yet sent)"
    )
    return {
        "status": "draft_only",
        "message": "This email has NOT been sent. It is a draft for the user to review and send themselves.",
        "to": to,
        "subject": subject,
        "body": body,
    }
