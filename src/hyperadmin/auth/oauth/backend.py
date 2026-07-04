"""The generic OAuth2 / OIDC backend.

:class:`OAuthBackend` is the engine room of HyperAdmin's federated sign-in. A single
implementation, parameterized by :class:`~hyperadmin.auth.oauth.providers.OAuthProviderConfig`,
talks to *any* OAuth2 / OIDC identity provider — Google and GitHub ship out of the box,
a third provider needs only configuration. See ``docs/specs/oauth-sso.md``.

This module owns three responsibilities, kept deliberately out of the view layer per
the Constitution (business logic does not live in handlers):

* :meth:`OAuthBackend.exchange_code` — swap an authorization ``code`` for tokens.
* :meth:`OAuthBackend.get_userinfo` — fetch the user profile, with a GitHub-private-email
  fallback to ``/user/emails``.
* :meth:`OAuthBackend.provision_user` — create or link a :class:`User` per the SDD's
  *interstitial* account-linking policy (never auto-link by email), persist the
  encrypted :class:`OAuthToken`, bridge to MFA, and forward-map the tenant claim.

HTTP is performed through an injectable ``client_factory`` so callers (and tests) can
supply a pre-configured (or mock-transport) :class:`httpx.AsyncClient`.
"""

from __future__ import annotations

import secrets
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from hyperadmin.auth.exceptions import (
    AccountExistsError,
    MFARequiredError,
    OAuthProviderError,
)
from hyperadmin.auth.models import OAuthToken, User  # type: ignore[attr-defined]

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

    from hyperadmin.auth.oauth.providers import OAuthProviderConfig

# Where an MFA-enabled user is sent after a successful OAuth login (partial-auth).
MFA_CHALLENGE_REDIRECT = "/admin/mfa/challenge"

# A typed alias for the optional host hook that maps a tenant claim value to a tenant id.
TenantResolver = Callable[[str], "int | str | None"]
ClientFactory = Callable[[], httpx.AsyncClient]


class OAuthBackend:
    """Token exchange, userinfo retrieval, and user provisioning for OAuth2 / OIDC.

    Args:
        providers: Mapping of provider name (``"google"``, ``"github"``, ...) to its
            :class:`OAuthProviderConfig`. The same name appears in callback URLs.
        engine: The application's async SQLAlchemy engine; used to read and write the
            ``User`` and ``OAuthToken`` rows during provisioning.
        client_factory: Returns an :class:`httpx.AsyncClient` per HTTP call. Defaults to
            a plain client; tests inject a mock-transport client for determinism.
        tenant_resolver: Optional host hook. When a provider sets ``tenant_id_claim`` and
            that claim is present in the userinfo, the resolver maps the claim value
            (e.g. a Google ``hd`` domain) to the tenant id assigned to a *new* user.
            Forward-compat with v0.5.3 multi-tenancy; the ``User`` model gains the
            ``tenant_id`` column there.
    """

    def __init__(
        self,
        providers: dict[str, OAuthProviderConfig],
        engine: AsyncEngine,
        *,
        client_factory: ClientFactory | None = None,
        tenant_resolver: TenantResolver | None = None,
    ) -> None:
        self.providers = providers
        self.engine = engine
        self._client_factory: ClientFactory = client_factory or httpx.AsyncClient
        self._tenant_resolver = tenant_resolver

    # ── Configuration access ──────────────────────────────────────────────────
    def get_provider(self, name: str) -> OAuthProviderConfig:
        """Return the configured provider, or raise :class:`OAuthProviderError`."""
        provider = self.providers.get(name)
        if provider is None:
            raise OAuthProviderError(name, "provider is not configured")
        return provider

    # ── Token exchange ────────────────────────────────────────────────────────
    async def exchange_code(
        self,
        provider: OAuthProviderConfig,
        code: str,
        redirect_uri: str,
        *,
        code_verifier: str | None = None,
    ) -> dict[str, Any]:
        """Exchange an authorization ``code`` for an access (and refresh) token.

        Sends the standard authorization-code grant to the provider's token endpoint.
        When ``code_verifier`` is supplied (PKCE ``S256`` flows) it is included so the
        provider can verify the challenge. GitHub returns form-encoded bodies unless an
        ``Accept: application/json`` header is sent, so the header is always set.

        Raises:
            OAuthProviderError: The provider returned a non-2xx response or a malformed
                token payload.
        """
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": provider.client_id,
            "client_secret": provider.client_secret,
        }
        if code_verifier is not None:
            data["code_verifier"] = code_verifier

        async with self._client_factory() as client:
            try:
                response = await client.post(
                    provider.token_url,
                    data=data,
                    headers={"Accept": "application/json"},
                )
            except httpx.HTTPError as exc:
                raise OAuthProviderError(provider.name, f"token request failed: {exc}") from exc

        if response.is_error:
            raise OAuthProviderError(
                provider.name,
                f"token exchange failed ({response.status_code}): {response.text[:200]}",
            )

        payload = self._parse_json(provider, response)
        if "error" in payload:
            raise OAuthProviderError(provider.name, f"token error: {payload['error']}")
        if not payload.get("access_token"):
            raise OAuthProviderError(provider.name, "token response missing access_token")
        return payload

    # ── Userinfo ──────────────────────────────────────────────────────────────
    async def get_userinfo(
        self, provider: OAuthProviderConfig, access_token: str
    ) -> dict[str, Any]:
        """Fetch the user profile for ``access_token`` from the provider.

        For GitHub (and any provider whose primary userinfo omits the email because the
        user keeps it private) this falls back to the ``/user/emails`` collection and
        selects the primary verified address. A provisioning-usable email is mandatory:
        if none is found, an :class:`OAuthProviderError` is raised.
        """
        async with self._client_factory() as client:
            userinfo = await self._fetch_userinfo(provider, client, access_token)
            email = self._extract_email(provider, userinfo)
            if not email:
                email = await self._fetch_fallback_email(provider, client, access_token)

        if not email:
            raise OAuthProviderError(
                provider.name,
                "the provider returned no usable email; grant the email scope",
            )
        userinfo[provider.email_claim] = email
        return userinfo

    async def _fetch_userinfo(
        self,
        provider: OAuthProviderConfig,
        client: httpx.AsyncClient,
        access_token: str,
    ) -> dict[str, Any]:
        try:
            response = await client.get(
                provider.userinfo_url,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                },
            )
        except httpx.HTTPError as exc:
            raise OAuthProviderError(provider.name, f"userinfo request failed: {exc}") from exc

        if response.is_error:
            raise OAuthProviderError(
                provider.name,
                f"userinfo request failed ({response.status_code})",
            )
        payload = self._parse_json(provider, response)
        if not isinstance(payload, dict):
            raise OAuthProviderError(provider.name, "userinfo response was not an object")
        return payload

    async def _fetch_fallback_email(
        self,
        provider: OAuthProviderConfig,
        client: httpx.AsyncClient,
        access_token: str,
    ) -> str | None:
        """Resolve a private GitHub-style email via the ``/user/emails`` endpoint."""
        emails_url = provider.userinfo_url.rstrip("/") + "/emails"
        try:
            response = await client.get(
                emails_url,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                },
            )
        except httpx.HTTPError:
            return None
        if response.is_error:
            return None
        try:
            entries = response.json()
        except ValueError:
            return None
        if not isinstance(entries, list):
            return None

        primary = next(
            (e for e in entries if e.get("primary") and e.get("verified")),
            None,
        )
        verified = next((e for e in entries if e.get("verified")), None)
        chosen = primary or verified or (entries[0] if entries else None)
        if isinstance(chosen, dict):
            email = chosen.get("email")
            return email if isinstance(email, str) else None
        return None

    # ── Provisioning ──────────────────────────────────────────────────────────
    async def provision_user(
        self,
        provider_name: str,
        userinfo: dict[str, Any],
        token_data: dict[str, Any],
    ) -> User:
        """Create or link a :class:`User` from ``userinfo`` and persist its OAuth token.

        Linking policy (per the SDD — never auto-link by email):

        * **Returning user** — a row already exists for ``(provider, sub)``: the existing
          user is reused and its token is refreshed.
        * **New identity, free email** — no existing user owns the email: a new
          OAuth-only user (``password_hash=None``) is created.
        * **New identity, taken email** — another account already owns the email:
          :class:`AccountExistsError` is raised (the view renders the link interstitial).

        After provisioning, if the resolved user has ``mfa_enabled`` set, an
        :class:`MFARequiredError` is raised so the view creates a partial-auth session.

        Raises:
            OAuthProviderError: ``provider_name`` is not configured.
            AccountExistsError: The email collides with a non-linked account.
            MFARequiredError: The user owes a second factor.
        """
        provider = self.get_provider(provider_name)
        sub = self._extract_sub(provider, userinfo)
        email = self._extract_email(provider, userinfo)
        if not email:
            raise OAuthProviderError(provider.name, "userinfo is missing an email claim")

        async with AsyncSession(self.engine) as session:
            existing_token = (
                await session.execute(
                    select(OAuthToken).where(
                        OAuthToken.provider == provider.name, OAuthToken.sub == sub
                    )
                )
            ).scalar_one_or_none()

            if existing_token is not None:
                user = await self._link_returning_user(session, existing_token, token_data)
            else:
                user = await self._provision_new_user(
                    session, provider, userinfo, email, sub, token_data
                )
            await session.commit()
            await session.refresh(user)
            mfa_enabled = bool(user.mfa_enabled)
            # Detach a stable copy before the session closes so callers can read fields.
            session.expunge(user)

        if mfa_enabled:
            raise MFARequiredError(user, MFA_CHALLENGE_REDIRECT)
        return user

    async def _link_returning_user(
        self,
        session: AsyncSession,
        token: OAuthToken,
        token_data: dict[str, Any],
    ) -> User:
        self._apply_token_data(token, token_data)
        session.add(token)
        user = (await session.execute(select(User).where(User.id == token.user_id))).scalar_one()
        return user

    async def _provision_new_user(
        self,
        session: AsyncSession,
        provider: OAuthProviderConfig,
        userinfo: dict[str, Any],
        email: str,
        sub: str,
        token_data: dict[str, Any],
    ) -> User:
        email_owner = (
            await session.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()
        if email_owner is not None:
            # Never auto-link: the email belongs to a local or other-identity account.
            raise AccountExistsError(email)

        user = User(
            username=await self._unique_username(session, email),
            email=email,
            password_hash=None,  # OAuth-only user — no local password.
            first_name=self._first_name(userinfo),
            last_name=self._last_name(userinfo),
            is_active=True,
        )
        self._apply_tenant(provider, userinfo, user)
        session.add(user)
        await session.flush()  # assign user.id before building the token row.

        token = OAuthToken(user_id=user.id, provider=provider.name, sub=sub)
        self._apply_token_data(token, token_data)
        session.add(token)
        return user

    # ── Field extraction & helpers ────────────────────────────────────────────
    def _extract_sub(self, provider: OAuthProviderConfig, userinfo: dict[str, Any]) -> str:
        raw = userinfo.get(provider.sub_claim)
        if raw is None or raw == "":
            raise OAuthProviderError(
                provider.name, f"userinfo is missing the {provider.sub_claim!r} subject claim"
            )
        return str(raw)

    def _extract_email(self, provider: OAuthProviderConfig, userinfo: dict[str, Any]) -> str | None:
        value = userinfo.get(provider.email_claim)
        return value if isinstance(value, str) and value else None

    def _apply_token_data(self, token: OAuthToken, token_data: dict[str, Any]) -> None:
        token.access_token = str(token_data["access_token"])
        refresh = token_data.get("refresh_token")
        token.refresh_token = str(refresh) if refresh else None
        token.scopes = self._parse_scopes(token_data.get("scope"))
        token.expires_at = self._compute_expiry(token_data.get("expires_in"))
        token.updated_at = datetime.now(timezone.utc)

    def _apply_tenant(
        self, provider: OAuthProviderConfig, userinfo: dict[str, Any], user: User
    ) -> None:
        """Forward-map the tenant claim onto a new user (v0.5.3 compat).

        Only consults the host resolver when the provider declares a ``tenant_id_claim``
        and that claim is present. The resolved value is stored on ``user.tenant_id`` if
        the model exposes that attribute (it does not in v0.5.2), so this is a no-op on
        the current schema beyond invoking the resolver.
        """
        if provider.tenant_id_claim is None or self._tenant_resolver is None:
            return
        claim_value = userinfo.get(provider.tenant_id_claim)
        if not isinstance(claim_value, str) or not claim_value:
            return
        tenant_id = self._tenant_resolver(claim_value)
        if tenant_id is not None and hasattr(user, "tenant_id"):
            user.tenant_id = tenant_id

    async def _unique_username(self, session: AsyncSession, email: str) -> str:
        base = email.split("@", 1)[0][:40] or "user"
        candidate = base
        while (
            await session.execute(select(User).where(User.username == candidate))
        ).scalar_one_or_none() is not None:
            candidate = f"{base[:32]}-{secrets.token_hex(4)}"
        return candidate

    @staticmethod
    def _first_name(userinfo: dict[str, Any]) -> str:
        given = userinfo.get("given_name")
        if isinstance(given, str):
            return given[:50]
        name = userinfo.get("name")
        if isinstance(name, str) and name.strip():
            return name.strip().split(" ", 1)[0][:50]
        return ""

    @staticmethod
    def _last_name(userinfo: dict[str, Any]) -> str:
        family = userinfo.get("family_name")
        if isinstance(family, str):
            return family[:50]
        name = userinfo.get("name")
        if isinstance(name, str) and " " in name.strip():
            return name.strip().split(" ", 1)[1][:50]
        return ""

    @staticmethod
    def _parse_scopes(scope: Any) -> list[str]:
        if isinstance(scope, str):
            # Google space-delimits, GitHub comma-delimits.
            separator = "," if "," in scope else " "
            return [s for s in scope.split(separator) if s]
        if isinstance(scope, list):
            return [str(s) for s in scope]
        return []

    @staticmethod
    def _compute_expiry(expires_in: Any) -> datetime | None:
        if isinstance(expires_in, (int, float)) and expires_in > 0:
            return datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
        return None

    @staticmethod
    def _parse_json(provider: OAuthProviderConfig, response: httpx.Response) -> Any:
        try:
            return response.json()
        except ValueError as exc:
            raise OAuthProviderError(
                provider.name, "provider returned a non-JSON response"
            ) from exc


__all__ = ["MFA_CHALLENGE_REDIRECT", "OAuthBackend"]
