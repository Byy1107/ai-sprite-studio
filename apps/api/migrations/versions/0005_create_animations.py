"""create animation clips and frames

Revision ID: 0005
Revises: 0004
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "animations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "asset_id", sa.String(36),
            sa.ForeignKey("assets.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("direction", sa.String(32), nullable=False),
        sa.Column("fps", sa.Integer(), nullable=False),
        sa.Column("loop_mode", sa.String(16), nullable=False),
        sa.Column("canvas_width", sa.Integer(), nullable=False),
        sa.Column("canvas_height", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_animations_asset_id", "animations", ["asset_id"])
    op.create_table(
        "animation_frames",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "animation_id", sa.String(36),
            sa.ForeignKey("animations.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "asset_version_id", sa.String(36),
            sa.ForeignKey("asset_versions.id", ondelete="RESTRICT"), nullable=False,
        ),
        sa.Column("frame_index", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("offset_x", sa.Integer(), nullable=False),
        sa.Column("offset_y", sa.Integer(), nullable=False),
        sa.Column("pivot_x", sa.Integer(), nullable=False),
        sa.Column("pivot_y", sa.Integer(), nullable=False),
        sa.Column("event_name", sa.String(80), nullable=True),
    )
    op.create_index("ix_animation_frames_animation_id", "animation_frames", ["animation_id"])


def downgrade() -> None:
    op.drop_index("ix_animation_frames_animation_id", table_name="animation_frames")
    op.drop_table("animation_frames")
    op.drop_index("ix_animations_asset_id", table_name="animations")
    op.drop_table("animations")
