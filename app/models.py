from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Service(Base):
    __tablename__ = "services"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    url: Mapped[str] = mapped_column(String(512))
    host: Mapped[str] = mapped_column(String(64), index=True)
    port: Mapped[int] = mapped_column(Integer)
    protocol: Mapped[str] = mapped_column(String(16), default="http")
    category: Mapped[str] = mapped_column(String(64), default="Inne")
    icon: Mapped[str] = mapped_column(String(64), default="globe")
    icon_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    auto_discovered: Mapped[bool] = mapped_column(Boolean, default=True)
    customized: Mapped[bool] = mapped_column(Boolean, default=False)
    has_login: Mapped[bool] = mapped_column(Boolean, default=False)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    is_online: Mapped[bool] = mapped_column(Boolean, default=True)
    health_detail: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_seen: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_checked: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    service_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    mac_address: Mapped[str | None] = mapped_column(String(17), nullable=True)
    wol_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    wol_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sol_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    broadcast_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    service: Mapped[str] = mapped_column(String(64), default="Inne")
    secret_encrypted: Mapped[str] = mapped_column(Text)
    secret_hint: Mapped[str] = mapped_column(String(16))
    username: Mapped[str | None] = mapped_column(String(128), nullable=True)
    url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text, default="")
    color: Mapped[str] = mapped_column(String(16), default="green")
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


DEFAULT_ABOUT_PROJECT = (
    "NetDash automatycznie skanuje sieć lokalną, identyfikuje serwisy webowe, "
    "przypisuje ikony marek (Jellyfin, Grafana, Plex…), rozdziela usługi z panelem logowania "
    "i oferuje zaszyfrowany sejf API keys oraz notatki. "
    "Inspirowany Homerem — ale bez ręcznego YAML."
)


class AppSettings(Base):
    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(64), default="NetDash")
    subtitle: Mapped[str] = mapped_column(String(256), default="Homelab dashboard z auto-wykrywaniem sieci")
    theme: Mapped[str] = mapped_column(String(16), default="midnight")
    accent_color: Mapped[str] = mapped_column(String(16), default="#22c55e")
    language: Mapped[str] = mapped_column(String(8), default="pl")
    author_name: Mapped[str] = mapped_column(String(64), default="lobrzut")
    author_bio: Mapped[str] = mapped_column(Text, default="")
    author_url: Mapped[str] = mapped_column(String(256), default="https://github.com/lobrzut")
    about_project: Mapped[str] = mapped_column(Text, default=DEFAULT_ABOUT_PROJECT)
    footer_text: Mapped[str] = mapped_column(String(256), default="")
    scan_cidr_default: Mapped[str | None] = mapped_column(String(512), nullable=True)
    full_scan_default: Mapped[bool] = mapped_column(Boolean, default=False)
    host_scan_ports: Mapped[str] = mapped_column(String(128), default="22,445,3389,5900")
    host_only_entries: Mapped[bool] = mapped_column(Boolean, default=True)
    show_vault: Mapped[bool] = mapped_column(Boolean, default=True)
    show_notes: Mapped[bool] = mapped_column(Boolean, default=True)
    show_about: Mapped[bool] = mapped_column(Boolean, default=False)
    show_clock: Mapped[bool] = mapped_column(Boolean, default=True)
    show_stats: Mapped[bool] = mapped_column(Boolean, default=True)
    services_columns: Mapped[str] = mapped_column(String(16), default="normal")
    show_category_filters: Mapped[bool] = mapped_column(Boolean, default=True)
    show_service_urls: Mapped[bool] = mapped_column(Boolean, default=True)
    show_ports: Mapped[bool] = mapped_column(Boolean, default=True)
    services_grouped: Mapped[bool] = mapped_column(Boolean, default=True)
    default_access_filter: Mapped[str] = mapped_column(String(16), default="all")
    card_style: Mapped[str] = mapped_column(String(16), default="detailed")
    custom_css: Mapped[str | None] = mapped_column(Text, nullable=True)
    favicon_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    use_custom_logo: Mapped[bool] = mapped_column(Boolean, default=False)
    custom_logo_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    wol_broadcast_ip: Mapped[str] = mapped_column(String(64), default="255.255.255.255")
    wol_port: Mapped[int] = mapped_column(Integer, default=9)
    sol_port: Mapped[int] = mapped_column(Integer, default=9)
    arp_scan_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    health_check_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    health_check_interval: Mapped[int] = mapped_column(Integer, default=60)
    gptwol_url: Mapped[str | None] = mapped_column(String(256), nullable=True)
    stale_remove_days: Mapped[int] = mapped_column(Integer, default=0)


class ScanJob(Base):
    __tablename__ = "scan_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cidr: Mapped[str] = mapped_column(String(512))
    status: Mapped[str] = mapped_column(String(32), default="pending")
    found_count: Mapped[int] = mapped_column(Integer, default=0)
    progress_phase: Mapped[str] = mapped_column(String(32), default="")
    progress_current: Mapped[int] = mapped_column(Integer, default=0)
    progress_total: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
