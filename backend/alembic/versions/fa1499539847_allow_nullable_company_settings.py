"""allow nullable company settings

Revision ID: fa1499539847
Revises: b10b63f2a9fb
Create Date: 2026-08-28 10:25:28.673483

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fa1499539847'
down_revision: Union[str, Sequence[str], None] = 'b10b63f2a9fb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "company_settings",
        "gst_number",
        existing_type=sa.String(length=32),
        nullable=True,
    )
    op.alter_column(
        "company_settings",
        "address",
        existing_type=sa.Text(),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "company_settings",
        "gst_number",
        existing_type=sa.String(length=32),
        nullable=False,
    )
    op.alter_column(
        "company_settings",
        "address",
        existing_type=sa.Text(),
        nullable=False,
    )
