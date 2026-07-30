"""SQLAlchemy models for IG Automation OS."""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from .database import Base


def _now():
    return datetime.now(timezone.utc)


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    account_name = Column(String(255), nullable=False, unique=True)
    profile_path = Column(String(500), nullable=False)
    # session_status: unknown | ready | expired
    session_status = Column(String(32), default="unknown", nullable=False)
    # account_status: enabled | disabled
    account_status = Column(String(32), default="enabled", nullable=False)
    last_used_at = Column(DateTime, nullable=True)
    last_successful_post_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_now, nullable=False)
    updated_at = Column(DateTime, default=_now, onupdate=_now, nullable=False)


class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, index=True)
    # content_type: reel | static
    content_type = Column(String(32), nullable=False)
    caption = Column(Text, default="", nullable=False)
    account_quantity = Column(Integer, nullable=False)
    # distribution_mode: same | one_per_account | round_robin
    distribution_mode = Column(String(32), nullable=False)
    # audio_mode: original | ig_music  (only meaningful for reels)
    audio_mode = Column(String(32), default="original", nullable=False)
    music_search = Column(String(500), default="", nullable=False)
    # status: draft | queued | running | paused | completed | partial | failed | stopped
    status = Column(String(32), default="draft", nullable=False)
    created_at = Column(DateTime, default=_now, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    files = relationship("CampaignFile", back_populates="campaign", cascade="all, delete-orphan")
    jobs = relationship("Job", back_populates="campaign", cascade="all, delete-orphan")


class CampaignFile(Base):
    __tablename__ = "campaign_files"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False)
    filename = Column(String(500), nullable=False)  # original name
    stored_path = Column(String(500), nullable=False)  # absolute path on disk
    file_type = Column(String(64), nullable=False)  # mime hint (video/mp4, image/png)
    size_bytes = Column(Integer, default=0, nullable=False)
    order_index = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=_now, nullable=False)

    campaign = relationship("Campaign", back_populates="files")


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)
    file_id = Column(Integer, ForeignKey("campaign_files.id"), nullable=True)
    # status: queued | processing | successful | failed | skipped
    status = Column(String(32), default="queued", nullable=False)
    attempt_count = Column(Integer, default=0, nullable=False)
    error_message = Column(Text, default="", nullable=False)
    created_at = Column(DateTime, default=_now, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    campaign = relationship("Campaign", back_populates="jobs")


class Setting(Base):
    __tablename__ = "settings"

    key = Column(String(128), primary_key=True)
    value = Column(Text, default="", nullable=False)
    updated_at = Column(DateTime, default=_now, onupdate=_now, nullable=False)


class LogEntry(Base):
    __tablename__ = "logs"

    id = Column(Integer, primary_key=True, index=True)
    # level: INFO | SUCCESS | WARNING | ERROR
    level = Column(String(16), nullable=False, default="INFO")
    message = Column(Text, nullable=False)
    campaign_id = Column(Integer, nullable=True)
    account_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=_now, nullable=False)
