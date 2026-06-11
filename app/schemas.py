from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.scanner import normalize_scan_cidr_list, parse_scan_cidrs


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    username: str
    password: str


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=4)


class ServiceCreate(BaseModel):
    name: str
    url: str
    category: str = "Inne"
    icon: str = "globe"
    icon_url: str | None = None
    description: str | None = None
    pinned: bool = False
    has_login: bool = False


class IconUploadResponse(BaseModel):
    url: str


class ServiceUpdate(BaseModel):
    name: str | None = None
    url: str | None = None
    category: str | None = None
    icon: str | None = None
    icon_url: str | None = None
    description: str | None = None
    pinned: bool | None = None
    has_login: bool | None = None
    service_notes: str | None = None
    mac_address: str | None = None
    wol_enabled: bool | None = None
    wol_port: int | None = None
    sol_port: int | None = None
    broadcast_ip: str | None = None


class ServiceIdentifyRequest(BaseModel):
    name: str | None = None
    url: str | None = None
    category: str | None = None
    icon: str | None = None
    icon_url: str | None = None
    description: str | None = None
    has_login: bool | None = None


class ServiceIdentifySuggestion(BaseModel):
    name: str | None = None
    url: str | None = None
    category: str | None = None
    icon: str | None = None
    icon_url: str | None = None
    description: str | None = None
    has_login: bool | None = None


class ServiceIdentifyResponse(BaseModel):
    matched: bool
    confidence: str
    matched_by: list[str] = Field(default_factory=list)
    heuristics: list[str] = Field(default_factory=list)
    changed_fields: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    note: str | None = None
    suggestion: ServiceIdentifySuggestion


class ServiceOut(BaseModel):
    id: int
    name: str
    url: str
    host: str
    port: int
    protocol: str
    category: str
    icon: str
    icon_url: str | None = None
    description: str | None
    auto_discovered: bool
    customized: bool = False
    has_login: bool
    pinned: bool
    is_online: bool = True
    health_detail: str | None = None
    last_seen: datetime
    last_checked: datetime | None = None
    service_notes: str | None = None
    mac_address: str | None = None
    wol_enabled: bool = False
    wol_port: int | None = None
    sol_port: int | None = None
    broadcast_ip: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class ScanRequest(BaseModel):
    cidr: str | None = Field(
        default=None,
        description="Sieć(e) w formacie CIDR — wiele oddzielonych przecinkiem lub nową linią",
    )
    full_scan: bool = Field(default=False, description="Skanuj wszystkie porty (wolniejsze)")

    @field_validator("cidr")
    @classmethod
    def validate_cidr(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        parse_scan_cidrs(value)
        return normalize_scan_cidr_list(value)


class ScanStatus(BaseModel):
    id: int
    cidr: str
    status: str
    found_count: int
    progress_phase: str = ""
    progress_current: int = 0
    progress_total: int = 0
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True


class NetworkInfo(BaseModel):
    local_network: str
    local_ip: str
    docker_bridge: bool = False
    scan_cidr_configured: bool = False


class AppSettingsOut(BaseModel):
    title: str
    subtitle: str
    theme: str = "midnight"
    accent_color: str
    language: str = "pl"
    author_name: str = "lobrzut"
    author_bio: str = ""
    author_url: str = ""
    about_project: str = ""
    footer_text: str = ""
    scan_cidr_default: str | None = None
    full_scan_default: bool = False
    host_scan_ports: str = "22,445,3389,5900"
    host_only_entries: bool = True
    show_vault: bool = True
    show_notes: bool = True
    show_about: bool = False
    show_clock: bool = True
    show_stats: bool = True
    services_columns: str = "normal"
    show_category_filters: bool = True
    show_service_urls: bool = True
    show_ports: bool = True
    services_grouped: bool = True
    default_access_filter: str = "all"
    card_style: str = "detailed"
    pinned_card_size: str = "medium"
    custom_css: str | None = None
    favicon_url: str | None = None
    use_custom_logo: bool = False
    custom_logo_url: str | None = None
    wol_broadcast_ip: str = "255.255.255.255"
    wol_port: int = 9
    sol_port: int = 9
    arp_scan_enabled: bool = True
    health_check_enabled: bool = True
    health_check_interval: int = 60
    gptwol_url: str | None = None
    stale_remove_days: int = 0

    class Config:
        from_attributes = True


class AppSettingsUpdate(BaseModel):
    title: str | None = None
    subtitle: str | None = None
    theme: str | None = None
    accent_color: str | None = None
    language: str | None = None
    author_name: str | None = None
    author_bio: str | None = None
    author_url: str | None = None
    about_project: str | None = None
    footer_text: str | None = None
    scan_cidr_default: str | None = None
    full_scan_default: bool | None = None
    host_scan_ports: str | None = None
    host_only_entries: bool | None = None
    show_vault: bool | None = None
    show_notes: bool | None = None
    show_about: bool | None = None
    show_clock: bool | None = None
    show_stats: bool | None = None
    services_columns: str | None = None
    show_category_filters: bool | None = None
    show_service_urls: bool | None = None
    show_ports: bool | None = None
    services_grouped: bool | None = None
    default_access_filter: str | None = None
    card_style: str | None = None
    pinned_card_size: str | None = None
    custom_css: str | None = None
    favicon_url: str | None = None
    use_custom_logo: bool | None = None
    custom_logo_url: str | None = None
    wol_broadcast_ip: str | None = None
    wol_port: int | None = None
    sol_port: int | None = None
    arp_scan_enabled: bool | None = None
    health_check_enabled: bool | None = None
    health_check_interval: int | None = None
    gptwol_url: str | None = None
    stale_remove_days: int | None = None

    @field_validator("scan_cidr_default")
    @classmethod
    def validate_scan_cidr_default(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        parse_scan_cidrs(value)
        return normalize_scan_cidr_list(value)


class PowerActionResult(BaseModel):
    ok: bool
    action: str
    message: str


class ArpScanRequest(BaseModel):
    cidr: str | None = Field(default=None, description="Opcjonalny CIDR; domyślnie lokalna sieć /24")


class ArpDeviceOut(BaseModel):
    ip: str
    mac: str
    hostname: str | None = None


class ArpLookupOut(BaseModel):
    ip: str
    mac: str | None = None
    found: bool = False


class ApiKeyCreate(BaseModel):
    name: str
    secret: str
    service: str = "Inne"
    username: str | None = None
    url: str | None = None
    notes: str | None = None
    pinned: bool = False


class ApiKeyUpdate(BaseModel):
    name: str | None = None
    secret: str | None = None
    service: str | None = None
    username: str | None = None
    url: str | None = None
    notes: str | None = None
    pinned: bool | None = None


class ApiKeyOut(BaseModel):
    id: int
    name: str
    service: str
    secret_masked: str
    secret_hint: str
    username: str | None
    url: str | None
    notes: str | None
    pinned: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ApiKeyReveal(BaseModel):
    secret: str


class NoteCreate(BaseModel):
    title: str
    content: str = ""
    color: str = "green"
    pinned: bool = False


class NoteUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    color: str | None = None
    pinned: bool | None = None


class NoteOut(BaseModel):
    id: int
    title: str
    content: str
    color: str
    pinned: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


BACKUP_FORMAT = "netdash-backup"
BACKUP_FORMAT_VERSION = 1


class SettingsBackupService(BaseModel):
    name: str
    url: str
    host: str | None = None
    port: int | None = None
    protocol: str = "http"
    category: str = "Inne"
    icon: str = "globe"
    icon_url: str | None = None
    description: str | None = None
    auto_discovered: bool = False
    has_login: bool = False
    pinned: bool = False
    service_notes: str | None = None
    mac_address: str | None = None
    wol_enabled: bool = False
    wol_port: int | None = None
    sol_port: int | None = None
    broadcast_ip: str | None = None


class SettingsBackupApiKey(BaseModel):
    name: str
    secret: str
    service: str = "Inne"
    username: str | None = None
    url: str | None = None
    notes: str | None = None
    pinned: bool = False


class SettingsBackupNote(BaseModel):
    title: str
    content: str = ""
    color: str = "green"
    pinned: bool = False


class SettingsBackupOut(BaseModel):
    format: str = BACKUP_FORMAT
    format_version: int = BACKUP_FORMAT_VERSION
    app_version: str
    exported_at: datetime
    settings: AppSettingsOut
    services: list[SettingsBackupService]
    api_keys: list[SettingsBackupApiKey]
    notes: list[SettingsBackupNote]


class SettingsImportRequest(BaseModel):
    format: str
    format_version: int
    settings: AppSettingsOut
    services: list[SettingsBackupService] = Field(default_factory=list)
    api_keys: list[SettingsBackupApiKey] = Field(default_factory=list)
    notes: list[SettingsBackupNote] = Field(default_factory=list)


class HomerImportResult(BaseModel):
    imported: int
    skipped: int = 0
    services: list[ServiceOut] = Field(default_factory=list)
