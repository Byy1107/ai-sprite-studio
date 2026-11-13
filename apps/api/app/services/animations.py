from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AnimationFrameRecord, AnimationRecord, AssetVersionRecord
from app.services.assets import AssetService


class AnimationNotFoundError(ValueError):
    pass


class AnimationService:
    def __init__(self, session: Session, assets: AssetService) -> None:
        self.session = session
        self.assets = assets

    def list_animations(self, asset_id: str) -> list[AnimationRecord]:
        self.assets.get_asset(asset_id)
        return list(self.session.scalars(
            select(AnimationRecord).where(AnimationRecord.asset_id == asset_id)
            .order_by(AnimationRecord.created_at, AnimationRecord.id)
        ))

    def get_animation(self, animation_id: str) -> AnimationRecord:
        animation = self.session.get(AnimationRecord, animation_id)
        if animation is None:
            raise AnimationNotFoundError("Animation was not found.")
        self.assets.get_asset(animation.asset_id)
        return animation

    def list_frames(self, animation_id: str) -> list[AnimationFrameRecord]:
        self.get_animation(animation_id)
        return list(self.session.scalars(
            select(AnimationFrameRecord)
            .where(AnimationFrameRecord.animation_id == animation_id)
            .order_by(AnimationFrameRecord.frame_index)
        ))

    def create_animation(
        self, asset_id: str, name: str, direction: str, fps: int, loop_mode: str
    ) -> AnimationRecord:
        asset = self.assets.get_asset(asset_id)
        if asset.asset_type != "character":
            raise ValueError("Movesets are available for character assets only.")
        if not name.strip() or not direction.strip():
            raise ValueError("Animation name and direction cannot be blank.")
        animation = AnimationRecord(
            asset_id=asset_id, name=name.strip(), direction=direction.strip(), fps=fps,
            loop_mode=loop_mode, canvas_width=asset.width, canvas_height=asset.height,
        )
        self.session.add(animation)
        self.session.commit()
        return animation

    def update_animation(self, animation_id: str, changes: dict[str, object]) -> AnimationRecord:
        animation = self.get_animation(animation_id)
        if any(
            isinstance(value, str) and not value.strip()
            for key, value in changes.items() if key in {"name", "direction"}
        ):
            raise ValueError("Animation name and direction cannot be blank.")
        for key, value in changes.items():
            setattr(animation, key, value.strip() if isinstance(value, str) else value)
        self.session.commit()
        return animation

    def delete_animation(self, animation_id: str) -> None:
        animation = self.get_animation(animation_id)
        for frame in self.list_frames(animation_id):
            self.session.delete(frame)
        self.session.delete(animation)
        self.session.commit()

    def add_frame(
        self, animation_id: str, version_id: str, duration_ms: int | None
    ) -> AnimationFrameRecord:
        animation = self.get_animation(animation_id)
        version = self.session.get(AssetVersionRecord, version_id)
        if version is None or version.asset_id != animation.asset_id:
            raise ValueError("Frame version must belong to this asset.")
        if (version.width, version.height) != (animation.canvas_width, animation.canvas_height):
            raise ValueError("Frame dimensions must match the animation canvas.")
        self.assets.get_version_path(version_id)
        frames = self.list_frames(animation_id)
        frame = AnimationFrameRecord(
            animation_id=animation_id, asset_version_id=version_id,
            frame_index=len(frames), duration_ms=duration_ms or round(1000 / animation.fps),
        )
        self.session.add(frame)
        self.session.commit()
        return frame

    def get_frame(self, frame_id: str) -> AnimationFrameRecord:
        frame = self.session.get(AnimationFrameRecord, frame_id)
        if frame is None:
            raise AnimationNotFoundError("Animation frame was not found.")
        self.get_animation(frame.animation_id)
        return frame

    def update_frame(self, frame_id: str, changes: dict[str, object]) -> AnimationFrameRecord:
        frame = self.get_frame(frame_id)
        for key, value in changes.items():
            setattr(frame, key, value)
        self.session.commit()
        return frame

    def delete_frame(self, frame_id: str) -> None:
        frame = self.get_frame(frame_id)
        animation_id = frame.animation_id
        self.session.delete(frame)
        self.session.flush()
        for index, remaining in enumerate(self.list_frames(animation_id)):
            remaining.frame_index = index
        self.session.commit()

    def duplicate_frame(self, frame_id: str) -> AnimationFrameRecord:
        source = self.get_frame(frame_id)
        frames = self.list_frames(source.animation_id)
        for frame in frames[source.frame_index + 1:]:
            frame.frame_index += 1
        duplicate = AnimationFrameRecord(
            animation_id=source.animation_id,
            asset_version_id=source.asset_version_id,
            frame_index=source.frame_index + 1,
            duration_ms=source.duration_ms,
            offset_x=source.offset_x,
            offset_y=source.offset_y,
            pivot_x=source.pivot_x,
            pivot_y=source.pivot_y,
            event_name=source.event_name,
        )
        self.session.add(duplicate)
        self.session.commit()
        return duplicate

    def reorder_frames(self, animation_id: str, frame_ids: list[str]) -> list[AnimationFrameRecord]:
        frames = self.list_frames(animation_id)
        if len(frame_ids) != len(frames) or set(frame_ids) != {frame.id for frame in frames}:
            raise ValueError("Reorder must include every frame exactly once.")
        by_id = {frame.id: frame for frame in frames}
        for index, frame_id in enumerate(frame_ids):
            by_id[frame_id].frame_index = index
        self.session.commit()
        return [by_id[frame_id] for frame_id in frame_ids]
