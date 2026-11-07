"""Security regression tests for shared approval requests."""

from app.api.routes.approvals import ApprovalCreate


def test_approval_requester_is_not_client_assignable():
    payload = ApprovalCreate(
        department_code="OPS",
        title="Leave / operational request",
        requested_by="forged-user",
    )

    # Extra client fields are ignored by the schema; the route derives the
    # persisted requester from the authenticated user instead.
    assert not hasattr(payload, "requested_by")
