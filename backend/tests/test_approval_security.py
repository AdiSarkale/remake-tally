"""Security regression tests for shared approval requests."""

import ast
from pathlib import Path


def test_approval_requester_is_not_client_assignable():
    route_path = Path(__file__).resolve().parents[1] / "app" / "api" / "routes" / "approvals.py"
    module = ast.parse(route_path.read_text(encoding="utf-8"))

    approval_create = next(
        node for node in module.body
        if isinstance(node, ast.ClassDef) and node.name == "ApprovalCreate"
    )
    declared_fields = {
        node.target.id
        for node in approval_create.body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    }
    assert "requested_by" not in declared_fields

    create_approval = next(
        node for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == "create_approval"
    )
    requester_assignments = [
        node for node in ast.walk(create_approval)
        if isinstance(node, ast.keyword) and node.arg == "requested_by"
    ]
    assert len(requester_assignments) == 1
    assert ast.unparse(requester_assignments[0].value) == "user.username"
