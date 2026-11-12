"""link asset versions to generation jobs

Revision ID: 0004
Revises: 0003
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("asset_versions") as batch:
        batch.add_column(sa.Column("generation_id", sa.String(36), nullable=True))
        batch.create_foreign_key(
            "fk_asset_versions_generation_id",
            "generation_jobs",
            ["generation_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("asset_versions") as batch:
        batch.drop_constraint("fk_asset_versions_generation_id", type_="foreignkey")
        batch.drop_column("generation_id")
