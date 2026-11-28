"""Link P0.1-09 candidate approvals to department Core approvals.
Revision ID: p0_hr_overtime_core_approval_025
Revises: p0_hr_overtime_workflow_024
"""
from alembic import op
import sqlalchemy as sa
revision="p0_hr_overtime_core_approval_025"
down_revision="p0_hr_overtime_workflow_024"
branch_labels=None
depends_on=None
def upgrade():
 op.add_column("hr_overtime_candidates",sa.Column("approval_request_id",sa.String(36),nullable=True))
 op.create_foreign_key("fk_hr_ot_candidate_approval_request","hr_overtime_candidates","approval_requests",["approval_request_id"],["id"],ondelete="RESTRICT")
 op.create_index("ix_hr_overtime_candidates_approval_request_id","hr_overtime_candidates",["approval_request_id"])
def downgrade():
 op.drop_index("ix_hr_overtime_candidates_approval_request_id",table_name="hr_overtime_candidates")
 op.drop_constraint("fk_hr_ot_candidate_approval_request","hr_overtime_candidates",type_="foreignkey")
 op.drop_column("hr_overtime_candidates","approval_request_id")
