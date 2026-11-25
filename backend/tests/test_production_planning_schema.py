"""Schema and route-registration regression coverage for production planning."""
from pathlib import Path
from alembic.config import Config
from alembic.script import ScriptDirectory
from app import models
from app.main import app

def test_planning_models_are_registered_in_shared_tenant_metadata():
    expected={
      "production_material_reservations","production_operation_schedules","machine_resources",
      "machine_downtime","production_costs","production_wip_stock","production_wip_movements","workcenter_shifts"
    }
    assert expected.issubset(set(models.Base.metadata.tables))

def test_production_planning_api_routes_are_registered():
    paths={route.path for route in app.routes}
    assert "/api/v1/manufacturing/planning/mrp/net-requirements" in paths
    assert "/api/v1/manufacturing/planning/orders/{order_id}/reservations" in paths
    assert "/api/v1/manufacturing/planning/orders/{order_id}/schedule" in paths
    assert "/api/v1/manufacturing/planning/analytics" in paths\n    assert "/api/v1/manufacturing/planning/wip/{wip_id}/consume" in paths\n    assert "/api/v1/manufacturing/planning/wip/{wip_id}/movements" in paths\n    assert "/api/v1/manufacturing/planning/costs/{production_entry_id}/auto" in paths\n    assert "/api/v1/manufacturing/planning/workcenters/{workcenter_id}/shifts" in paths\n    assert "/api/v1/manufacturing/planning/workcenters/{workcenter_id}/cost-rates" in paths
    assert "/api/v1/manufacturing/planning/downtime/{downtime_id}/close" in paths

def test_production_planning_migration_is_single_latest_head():
    config=Config(str(Path(__file__).resolve().parents[1]/"alembic.ini"))
    script=ScriptDirectory.from_config(config)
    assert script.get_heads()==["production_planning_007"]
    assert script.get_revision("production_planning_007").down_revision=="hr_timezone_006"
