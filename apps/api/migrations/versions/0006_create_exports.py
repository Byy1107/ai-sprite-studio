"""create export records

Revision ID: 0006
Revises: 0005
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "export_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id", sa.String(36),
            sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "asset_id", sa.String(36),
            sa.ForeignKey("assets.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("format", sa.String(24), nullable=False),
        sa.Column("preset_id", sa.String(80), nullable=True),
        sa.Column("config_json", sa.Text(), nullable=False),
        sa.Column("output_path", sa.Text(), nullable=False, unique=True),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_export_records_project_id", "export_records", ["project_id"])
    op.create_index("ix_export_records_asset_id", "export_records", ["asset_id"])


def downgrade() -> None:
    op.drop_index("ix_export_records_asset_id", table_name="export_records")
    op.drop_index("ix_export_records_project_id", table_name="export_records")
    op.drop_table("export_records")
