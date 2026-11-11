"""Create assets and asset versions."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("asset_type", sa.String(24), nullable=False),
        sa.Column("style", sa.String(24), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("color_mode", sa.String(16), nullable=False),
        sa.Column("active_version_id", sa.String(36), nullable=True),
        sa.Column("thumbnail_path", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_assets_project_id", "assets", ["project_id"])
    op.create_table(
        "asset_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "asset_id",
            sa.String(36),
            sa.ForeignKey("assets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("parent_version_id", sa.String(36), nullable=True),
        sa.Column("file_path", sa.Text(), nullable=False, unique=True),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(24), nullable=False),
        sa.Column("change_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_asset_versions_asset_id", "asset_versions", ["asset_id"])


def downgrade() -> None:
    op.drop_index("ix_asset_versions_asset_id", table_name="asset_versions")
    op.drop_table("asset_versions")
    op.drop_index("ix_assets_project_id", table_name="assets")
    op.drop_table("assets")
