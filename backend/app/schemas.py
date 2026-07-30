"""Pydantic schemas for API I/O."""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    account_name: str
    profile_path: str
    session_status: str
    account_status: str
    last_used_at: Optional[datetime] = None
    last_successful_post_at: Optional[datetime] = None
    created_at: datetime


class AccountCreate(BaseModel):
    account_name: str = Field(min_length=1, max_length=255)


class AccountUpdate(BaseModel):
    account_status: Optional[str] = None
    session_status: Optional[str] = None


class CampaignFileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    filename: str
    file_type: str
    size_bytes: int
    order_index: int


class CampaignCreate(BaseModel):
    content_type: str  # reel | static
    caption: str = ""
    account_quantity: int = Field(gt=0, le=10000)
    distribution_mode: str  # same | one_per_account | round_robin
    audio_mode: str = "original"  # original | ig_music
    music_search: str = ""
    file_ids: List[int] = []


class CampaignOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    content_type: str
    caption: str
    account_quantity: int
    distribution_mode: str
    audio_mode: str
    music_search: str
    status: str
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class CampaignDetail(CampaignOut):
    files: List[CampaignFileOut] = []
    job_counts: dict = {}


class SettingOut(BaseModel):
    key: str
    value: str


class SettingsUpdate(BaseModel):
    concurrent_workers: Optional[str] = None
    delay_between_jobs_seconds: Optional[str] = None
    max_retries: Optional[str] = None
    browser_headless: Optional[str] = None
    browser_timeout_seconds: Optional[str] = None
    profiles_dir: Optional[str] = None
    uploads_dir: Optional[str] = None
    logs_dir: Optional[str] = None


class LogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    level: str
    message: str
    campaign_id: Optional[int] = None
    account_id: Optional[int] = None
    created_at: datetime
