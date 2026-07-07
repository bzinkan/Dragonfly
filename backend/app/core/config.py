"""Typed application settings."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal, cast
from urllib.parse import quote, quote_plus

from fastapi import Request
from pydantic import Field
from pydantic_settings import (
    BaseSettings,
    DotEnvSettingsSource,
    EnvSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

Environment = Literal["local", "dev", "staging", "prod"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


def _default_cors_origins() -> list[str]:
    return ["http://localhost:19006"]


class Settings(BaseSettings):
    """Environment-driven configuration.

    `HINTERLAND_` is the primary prefix. `DRAGONFLY_` remains a fallback
    during the repo/environment rename so the old Azure environment can keep
    running until intentionally retired.
    """

    model_config = SettingsConfigDict(
        env_prefix="HINTERLAND_",
        env_file=".env",
        extra="ignore",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        env_file = settings_cls.model_config.get("env_file")
        env_file_encoding = settings_cls.model_config.get("env_file_encoding")
        return (
            init_settings,
            EnvSettingsSource(settings_cls, env_prefix="HINTERLAND_"),
            EnvSettingsSource(settings_cls, env_prefix="DRAGONFLY_"),
            DotEnvSettingsSource(
                settings_cls,
                env_file=env_file,
                env_file_encoding=env_file_encoding,
                env_prefix="HINTERLAND_",
            ),
            DotEnvSettingsSource(
                settings_cls,
                env_file=env_file,
                env_file_encoding=env_file_encoding,
                env_prefix="DRAGONFLY_",
            ),
            file_secret_settings,
        )

    app_name: str = "The Hinterland Guide API"
    app_version: str = "0.1.0"
    env: Environment = "local"
    log_level: LogLevel = "INFO"
    cors_origins: list[str] = Field(default_factory=_default_cors_origins)

    photos_bucket: str = "photos"

    # Object-storage backend. "noop" falls through to a fake impl in
    # tests (set explicitly via app.state.signed_url_generator).
    # "blob" uses Azure Blob Storage with user-delegation SAS URLs
    # minted via the Container Apps managed identity (Storage Blob
    # Data Contributor on the account).
    storage_provider: Literal["noop", "blob"] = "blob"
    blob_account_endpoint: str = ""

    # Microsoft Entra External ID adult auth. The verifier is JWKS-only via
    # PyJWT; MSAL lives in the mobile/web client.
    entra_tenant_id: str = "18dbd7fa-c411-49bc-82fc-9ccaa26e3404"
    entra_api_audience: str = "api://hinterland-api"
    entra_issuer: str = (
        "https://login.microsoftonline.com/18dbd7fa-c411-49bc-82fc-9ccaa26e3404/v2.0"
    )
    entra_jwks_url: str = (
        "https://login.microsoftonline.com/18dbd7fa-c411-49bc-82fc-9ccaa26e3404/discovery/v2.0/keys"
    )

    # Hinterland RS256 kid JWTs (handoff + session). Backend mints and
    # verifies these locally; the kid app stores the session JWT and sends
    # it as a Bearer token. JWKS is published under /.well-known/.
    kid_jwt_issuer: str = "https://api.thehinterlandguide.app"
    kid_jwt_audience: str = "hinterland-api"
    kid_jwt_kid: str = "k1-2026-07"
    kid_handoff_ttl_seconds: int = 900  # 15 minutes
    kid_session_ttl_seconds: int = 60 * 60 * 24 * 30  # 30 days

    # Azure Key Vault holding the kid-JWT signing PEM (RS256). Read once
    # per process via DefaultAzureCredential (UAMI in Container Apps).
    key_vault_url: str = "https://hinterland-kv-dev.vault.azure.net/"
    key_vault_kid_signing_secret: str = "kid-jwt-signing-key"
    key_vault_kid_public_secret: str = "kid-jwt-public-key"

    # Local fallbacks for tests / dev runs without Key Vault access. When
    # set, key_vault reads from these env vars instead of hitting AKV.
    kid_jwt_signing_pem: str = ""
    kid_jwt_public_pem: str = ""

    # Backend-augmented claim cache (Option C). Lookups for role +
    # group_id are short-circuited from a per-process TTLCache to keep
    # the per-request DB hit bounded.
    user_claims_cache_ttl_seconds: float = 30.0
    user_claims_cache_max_size: int = 1024

    # Development-only auth bypass. When enabled outside prod, missing bearer
    # tokens or this exact token resolve to a local dev kid user. This is for
    # device iteration only; leave disabled in shared/prod runtimes unless the
    # operator explicitly accepts that every caller gets the dev identity.
    dev_auth_enabled: bool = False
    dev_auth_token: str = "hinterland-dev-bypass"
    dev_auth_user_id: str = "01J0KIDID0000000000000ULID"
    dev_auth_group_id: str = "01J0GROUPID00000000000ULID"
    dev_auth_membership_id: str = "01J0MEMBERID0000000000ULID"
    dev_auth_display_name: str = "Dev Explorer"
    dev_auth_group_name: str = "Dev Backyard"

    # iNaturalist API integration. Token is empty in dev / CI; the iNat client
    # treats absence of a token as "no third-party calls allowed" and CV
    # endpoints return a `cv_unavailable` flag instead of raising.
    inat_base_url: str = "https://api.inaturalist.org/v1"
    inat_oauth_token: str = ""
    inat_request_timeout_seconds: float = 8.0

    # Outbound iNat submission posture. Defaults to False per the
    # Option B decision (2026-06-04): The Hinterland Guide does NOT post kid
    # observations to iNaturalist while the kid is under 13 because
    # iNat's standard ToS requires users to be 13+. Observations stay
    # in The Hinterland Guide until the kid claims them via the Phase 3 age-13
    # iNat-claim flow.
    #
    # When False the moderation worker / review-queue approve handler
    # skip writing the `inat_submit_outbox` row entirely; the Service
    # Bus consumer is dormant and the queue stays empty. The
    # infrastructure (queues, jobs, alerts) stays provisioned so
    # flipping this flag back on is a zero-deploy operator action.
    #
    # iNat CV (the read-only species identify endpoint) is unaffected
    # -- it never posts; the `inat_oauth_token` setting still wires
    # rate limits for it.
    inat_submit_enabled: bool = False

    # Reverse-geocoding provider. "noop" returns None for every lookup --
    # the kid sees no place_name; the observation itself still saves.
    # "nominatim" hits the public Nominatim instance (1 req/sec, no
    # commercial use); fine for dev. Production needs a contracted
    # provider (Google Maps, self-hosted Nominatim) per `docs/runbook.md`.
    geocoding_provider: Literal["noop", "nominatim"] = "noop"
    geocoding_nominatim_base_url: str = "https://nominatim.openstreetmap.org"
    geocoding_user_agent: str = (
        "TheHinterlandGuide/0.1 (+https://thehinterlandguide.app)"
    )
    geocoding_request_timeout_seconds: float = 5.0

    # Photo moderation. Production gate is Azure AI Content Safety.
    # Dev / CI default to "noop" -- every photo is treated as clean.
    moderation_provider: Literal["noop", "azure_content_safety"] = "noop"

    # Azure AI Content Safety wiring (Phase 6c). Severity 0-6: 4 / Medium
    # is the quarantine threshold per ADR 0010. Endpoint + key are pulled
    # from Key Vault secrets `content-safety-endpoint` /
    # `content-safety-key` and surfaced as env vars at Container App
    # boot time.
    content_safety_endpoint: str = ""
    content_safety_key: str = ""
    content_safety_severity_threshold: int = 4
    content_safety_request_timeout_seconds: float = 8.0

    # Internal-route OIDC auth. The `/internal/*` routes are called by
    # platform infrastructure (Eventarc / Cloud Tasks / Cloud Scheduler)
    # via Google-signed OIDC ID tokens. Production-safe default is
    # fail-closed: if `internal_oidc_required` is left None, the
    # `require_internal_oidc` property requires OIDC on any env that
    # isn't `local`. Local dev opts out so smoke scripts + the moderation
    # processor unit tests don't need a Google identity.
    internal_oidc_required: bool | None = None
    internal_oidc_audience: str = ""
    internal_oidc_allowed_service_accounts: list[str] = Field(default_factory=list)

    # Azure Service Bus for the iNat-submit transactional outbox (Risk
    # 0002 closure). Namespace is the FQDN
    # (e.g. `hinterland-sb-dev.servicebus.windows.net`); empty namespace
    # means "Service Bus not provisioned yet" -- the enqueue helper
    # returns success=False with `not_configured`, the outbox row stays
    # `pending`, and the 15-min replay job picks it up once provisioning
    # lands. Production auth is the Container App managed identity via
    # DefaultAzureCredential (no connection string).
    service_bus_namespace: str = ""
    service_bus_inat_queue: str = "inat-submit"
    service_bus_moderation_queue: str = "moderation-pending"
    service_bus_request_timeout_seconds: float = 8.0
    # Max messages a Service Bus consumer pulls per receive call. Keep
    # small so a stuck handler doesn't lock too many messages at once.
    service_bus_receive_batch_size: int = 8
    # Per-message lock duration grant; renewed on each receive cycle.
    # Service Bus default is 60s, but the moderation worker can take a
    # full Azure Content Safety roundtrip + Blob copy on slow images.
    service_bus_receive_max_wait_seconds: float = 30.0

    @property
    def service_bus_enabled(self) -> bool:
        """True when the producer can attempt to enqueue Service Bus messages.

        Empty namespace is the explicit "not provisioned yet" signal --
        producers gracefully no-op and leave outbox rows in `pending`
        for the replay job to retry once infra catches up.
        """
        return bool(self.service_bus_namespace)

    @property
    def require_internal_oidc(self) -> bool:
        """True when internal routes must enforce Google OIDC.

        Explicit override (`HINTERLAND_INTERNAL_OIDC_REQUIRED=true|false`,
        with `DRAGONFLY_INTERNAL_OIDC_REQUIRED` fallback)
        wins. Otherwise, anything past `local` fails closed.
        """
        if self.internal_oidc_required is not None:
            return self.internal_oidc_required
        return self.env != "local"

    cloud_sql_instance: str = ""
    database_host: str = "localhost"
    database_port: int = 5432
    database_name: str = "hinterland"
    database_user: str = "hinterland"
    database_password: str = "hinterland"
    database_password_secret: str = ""
    database_pool_size: int = 5
    database_max_overflow: int = 2
    database_echo_sql: bool = False
    readiness_database_required: bool = False

    @property
    def database_configured(self) -> bool:
        return bool(self.cloud_sql_instance or self.database_host)

    @property
    def sqlalchemy_database_url(self) -> str:
        """Build an async SQLAlchemy URL for local or managed Postgres."""
        user = quote_plus(self.database_user)
        password = quote_plus(self.database_password)
        database = quote_plus(self.database_name)

        if self.database_host.startswith("/"):
            socket_host = quote(self.database_host, safe="")
            return f"postgresql+asyncpg://{user}:{password}@/{database}?host={socket_host}"

        host = quote_plus(self.database_host)
        return f"postgresql+asyncpg://{user}:{password}@{host}:{self.database_port}/{database}"

    @property
    def dragonfly_jwt_issuer(self) -> str:
        """Legacy alias for code/tests not yet renamed."""
        return self.kid_jwt_issuer

    @property
    def dragonfly_jwt_audience(self) -> str:
        """Legacy alias for code/tests not yet renamed."""
        return self.kid_jwt_audience

    @property
    def dragonfly_jwt_kid(self) -> str:
        """Legacy alias for code/tests not yet renamed."""
        return self.kid_jwt_kid

    @property
    def dragonfly_handoff_ttl_seconds(self) -> int:
        """Legacy alias for code/tests not yet renamed."""
        return self.kid_handoff_ttl_seconds

    @property
    def dragonfly_session_ttl_seconds(self) -> int:
        """Legacy alias for code/tests not yet renamed."""
        return self.kid_session_ttl_seconds


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_request_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)
