"""
DATA-AI 企业级 — SSO / OIDC / SAML 认证集成

企业痛点:
- 不能给每个员工开 DATA-AI 账号 → 接企业 IdP (Okta/Azure AD/Auth0/Keycloak)
- SCIM 自动 provisioning
- JIT (Just-In-Time) 用户创建
- 域账号白名单 (only @company.com 可登录)
- 会话管理 (强制 MFA / IP 白名单 / 时段限制)

设计:
- IdentityProvider: 配置 (OIDC/SAML/LDAP)
- SSOProvider: 抽象接口
- OIDCProvider: OIDC 协议实现
- SAMLProvider: SAML 2.0 (简化)
- SCIMProvisioner: 自动开户/销户
- SessionStore: 登录会话
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlencode

ProviderType = Literal["oidc", "saml", "ldap"]


@dataclass
class IdentityProvider:
    """IdP 配置"""

    id: str = field(default_factory=lambda: f"idp-{uuid.uuid4().hex[:8]}")
    name: str = ""  # e.g. "Company Okta"
    type: ProviderType = "oidc"
    issuer: str = ""  # https://company.okta.com
    client_id: str = ""
    client_secret: str = ""  # 生产请用 KMS 加密存储
    authorization_endpoint: str = ""
    token_endpoint: str = ""
    userinfo_endpoint: str = ""
    jwks_uri: str = ""
    scopes: list[str] = field(default_factory=lambda: ["openid", "email", "profile"])
    # 域白名单 — 仅允许特定邮箱后缀
    allowed_email_domains: list[str] = field(default_factory=list)
    # 默认角色
    default_role: str = "member"
    # 自动 provisioning
    auto_provision: bool = True
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> IdentityProvider:
        return cls(**d)


@dataclass
class SSOSession:
    """SSO 登录会话"""

    id: str = field(default_factory=lambda: f"sess-{uuid.uuid4().hex[:16]}")
    user_id: str = ""
    email: str = ""
    tenant_id: str = ""
    idp_id: str = ""
    provider_type: ProviderType = "oidc"
    access_token: str = ""
    refresh_token: str = ""
    id_token: str = ""
    expires_at: float = 0.0
    ip: str = ""
    user_agent: str = ""
    mfa_verified: bool = False
    created_at: float = field(default_factory=time.time)
    last_used_at: float = field(default_factory=time.time)

    def is_expired(self) -> bool:
        return time.time() > self.expires_at

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SSOSession:
        return cls(**d)


# ============================================================================
# OIDC Provider
# ============================================================================


class OIDCProvider:
    """OIDC 提供方 — 负责生成 auth URL,验证 token,获取 userinfo"""

    def __init__(self, idp: IdentityProvider) -> None:
        self.idp = idp

    def build_authorization_url(self, redirect_uri: str, state: str = "", nonce: str = "") -> str:
        """构建 OIDC authorize URL"""
        params = {
            "response_type": "code",
            "client_id": self.idp.client_id,
            "redirect_uri": redirect_uri,
            "scope": " ".join(self.idp.scopes),
            "state": state or secrets.token_urlsafe(16),
            "nonce": nonce or secrets.token_urlsafe(16),
        }
        return f"{self.idp.authorization_endpoint}?{urlencode(params)}"

    def verify_id_token(self, id_token: str) -> dict[str, Any]:
        """验证 id_token — 简化版,生产需用 JWKS + 验签

        这里做基础检查:
        - iss 必须匹配 idp.issuer
        - aud 必须匹配 client_id
        - exp 必须未过期
        - 邮箱必须在 allowed_email_domains
        """
        # id_token 实际是 JWT — 这里做轻量解码
        try:
            parts = id_token.split(".")
            if len(parts) != 3:
                return {"ok": False, "error": "malformed id_token"}
            import base64

            payload = json.loads(base64.urlsafe_b64decode(parts[1] + "==="))
        except Exception as e:
            return {"ok": False, "error": f"decode failed: {e}"}

        # iss
        if payload.get("iss") != self.idp.issuer:
            return {"ok": False, "error": f"issuer mismatch: {payload.get('iss')}"}
        # aud
        aud = payload.get("aud")
        if aud != self.idp.client_id:
            return {"ok": False, "error": f"audience mismatch: {aud}"}
        # exp
        now = time.time()
        if payload.get("exp", 0) < now:
            return {"ok": False, "error": "id_token expired"}
        # 域白名单
        email = payload.get("email", "")
        if self.idp.allowed_email_domains:
            domain = email.split("@")[-1] if "@" in email else ""
            if domain not in self.idp.allowed_email_domains:
                return {"ok": False, "error": f"email domain not allowed: {domain}"}
        return {
            "ok": True,
            "sub": payload.get("sub"),
            "email": email,
            "name": payload.get("name", ""),
            "groups": payload.get("groups", []),
        }

    def exchange_code(self, code: str, redirect_uri: str) -> dict[str, Any]:
        """code → token (生产实际 POST 到 token_endpoint)"""
        # 简化: 假设 IdP 总是返回成功(测试用)
        # 真实场景需要:
        #   1) POST {token_endpoint} with grant_type=authorization_code
        #   2) 获取 access_token / refresh_token / id_token
        return {
            "ok": True,
            "access_token": f"sim-at-{secrets.token_hex(8)}",
            "refresh_token": f"sim-rt-{secrets.token_hex(8)}",
            "id_token": _make_test_jwt(self.idp, sub="user-123", email="alice@company.com", name="Alice"),
            "expires_in": 3600,
        }


def _make_test_jwt(idp: IdentityProvider, sub: str, email: str, name: str) -> str:
    """生成测试 JWT (生产请用真实 IdP 返回)"""
    import base64

    header = base64.urlsafe_b64encode(json.dumps({"alg": "RS256", "typ": "JWT"}).encode()).decode().rstrip("=")
    now = int(time.time())
    payload = (
        base64.urlsafe_b64encode(
            json.dumps(
                {
                    "iss": idp.issuer,
                    "aud": idp.client_id,
                    "sub": sub,
                    "email": email,
                    "name": name,
                    "iat": now,
                    "exp": now + 3600,
                }
            ).encode()
        )
        .decode()
        .rstrip("=")
    )
    # 签名简化: 用 client_secret HMAC
    sig = (
        base64.urlsafe_b64encode(
            hmac.new(idp.client_secret.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
        )
        .decode()
        .rstrip("=")
    )
    return f"{header}.{payload}.{sig}"


# ============================================================================
# SAML Provider (简化)
# ============================================================================


@dataclass
class SAMLConfig:
    sso_url: str = ""
    entity_id: str = ""
    x509_cert: str = ""


class SAMLProvider:
    """SAML 2.0 (简化,无完整 XML 解析)"""

    def __init__(self, idp: IdentityProvider, sp_config: SAMLConfig) -> None:
        self.idp = idp
        self.config = sp_config

    def build_authn_request(self) -> str:
        """构建 SAML AuthnRequest URL (简化)"""
        return f"{self.idp.authorization_endpoint}?SAMLRequest=..."


# ============================================================================
# SCIM Provisioner
# ============================================================================


@dataclass
class SCIMUser:
    """SCIM 2.0 用户"""

    id: str = field(default_factory=lambda: f"scim-{uuid.uuid4().hex[:12]}")
    user_name: str = ""  # email
    display_name: str = ""
    active: bool = True
    emails: list[dict[str, str]] = field(default_factory=list)
    groups: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_modified: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SCIMUser:
        return cls(**d)


class SCIMProvisioner:
    """SCIM 自动 provisioning — IdP 推送用户变更"""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._users: dict[str, SCIMUser] = {}

    def upsert_user(
        self, user_name: str, display_name: str = "", active: bool = True, groups: list[str] | None = None
    ) -> SCIMUser:
        with self._lock:
            for u in self._users.values():
                if u.user_name == user_name:
                    u.display_name = display_name
                    u.active = active
                    u.groups = groups or []
                    u.last_modified = time.time()
                    return u
            u = SCIMUser(
                user_name=user_name,
                display_name=display_name,
                active=active,
                groups=groups or [],
                emails=[{"value": user_name, "primary": True}],
            )
            self._users[u.id] = u
            return u

    def deactivate(self, user_name: str) -> bool:
        with self._lock:
            for u in self._users.values():
                if u.user_name == user_name:
                    u.active = False
                    u.last_modified = time.time()
                    return True
            return False

    def list_users(self, active_only: bool = False) -> list[SCIMUser]:
        with self._lock:
            out = list(self._users.values())
            if active_only:
                out = [u for u in out if u.active]
            return out

    def get_user(self, user_name: str) -> SCIMUser | None:
        for u in self._users.values():
            if u.user_name == user_name:
                return u
        return None


# ============================================================================
# Session Store
# ============================================================================


class SessionStore:
    """SSO 会话存储"""

    def __init__(self, persist_path: Path | None = None) -> None:
        self._lock = threading.RLock()
        self._sessions: dict[str, SSOSession] = {}
        self._persist_path = persist_path
        if persist_path:
            persist_path.parent.mkdir(parents=True, exist_ok=True)
            self._load_from_disk()

    def create(
        self,
        user_id: str,
        email: str,
        tenant_id: str,
        idp_id: str,
        provider_type: ProviderType,
        access_token: str,
        refresh_token: str,
        id_token: str,
        expires_in: int,
        ip: str = "",
        user_agent: str = "",
    ) -> SSOSession:
        with self._lock:
            sess = SSOSession(
                user_id=user_id,
                email=email,
                tenant_id=tenant_id,
                idp_id=idp_id,
                provider_type=provider_type,
                access_token=access_token,
                refresh_token=refresh_token,
                id_token=id_token,
                expires_at=time.time() + expires_in,
                ip=ip,
                user_agent=user_agent,
            )
            self._sessions[sess.id] = sess
            return sess

    def get(self, session_id: str) -> SSOSession | None:
        with self._lock:
            s = self._sessions.get(session_id)
            if not s:
                return None
            if s.is_expired():
                self._sessions.pop(session_id, None)
                return None
            s.last_used_at = time.time()
            return s

    def revoke(self, session_id: str) -> bool:
        with self._lock:
            return self._sessions.pop(session_id, None) is not None

    def revoke_user(self, user_id: str) -> int:
        with self._lock:
            n = 0
            for sid in list(self._sessions.keys()):
                if self._sessions[sid].user_id == user_id:
                    del self._sessions[sid]
                    n += 1
            return n

    def cleanup_expired(self) -> int:
        with self._lock:
            n = 0
            for sid in list(self._sessions.keys()):
                if self._sessions[sid].is_expired():
                    del self._sessions[sid]
                    n += 1
            return n

    def list_sessions(self, user_id: str = "") -> list[SSOSession]:
        with self._lock:
            out = list(self._sessions.values())
            if user_id:
                out = [s for s in out if s.user_id == user_id]
            return out

    def _load_from_disk(self) -> None:
        if not self._persist_path or not self._persist_path.exists():
            return
        try:
            with self._persist_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        s = SSOSession.from_dict(json.loads(line))
                        if not s.is_expired():
                            self._sessions[s.id] = s
                    except Exception:
                        continue
        except Exception:
            pass


# ============================================================================
# 主引擎
# ============================================================================


class SSOEngine:
    """SSO 引擎 — IdP 注册 + OIDC 流程 + SCIM + 会话"""

    def __init__(self, persist_path: Path | None = None) -> None:
        self._lock = threading.RLock()
        self._idps: dict[str, IdentityProvider] = {}
        self._session_store = SessionStore(persist_path=persist_path / "sessions.jsonl" if persist_path else None)
        self._scim = SCIMProvisioner()
        self._persist_path = persist_path
        if persist_path:
            persist_path.parent.mkdir(parents=True, exist_ok=True)
            self._load_from_disk()

    # ---------- IdP CRUD ----------
    def register_idp(self, idp: IdentityProvider) -> IdentityProvider:
        with self._lock:
            self._idps[idp.id] = idp
            self._write_idp(idp)
            return idp

    def list_idps(self) -> list[IdentityProvider]:
        with self._lock:
            return list(self._idps.values())

    def get_idp(self, idp_id: str) -> IdentityProvider | None:
        return self._idps.get(idp_id)

    def get_idp_by_name(self, name: str) -> IdentityProvider | None:
        for idp in self._idps.values():
            if idp.name == name:
                return idp
        return None

    def update_idp(self, idp_id: str, **kwargs: Any) -> IdentityProvider | None:
        with self._lock:
            idp = self._idps.get(idp_id)
            if not idp:
                return None
            for k, v in kwargs.items():
                if hasattr(idp, k):
                    setattr(idp, k, v)
            return idp

    def delete_idp(self, idp_id: str) -> bool:
        with self._lock:
            return self._idps.pop(idp_id, None) is not None

    # ---------- OIDC 流程 ----------
    def get_provider(self, idp_id: str) -> OIDCProvider | SAMLProvider | None:
        idp = self._idps.get(idp_id)
        if not idp:
            return None
        if idp.type == "oidc":
            return OIDCProvider(idp)
        if idp.type == "saml":
            return SAMLProvider(idp, SAMLConfig())
        return None

    def complete_login(
        self, idp_id: str, code: str, redirect_uri: str, tenant_id: str = "", ip: str = "", user_agent: str = ""
    ) -> dict[str, Any]:
        """完成 OIDC 登录 — 验证 id_token, 创建会话, 自动 provisioning"""
        with self._lock:
            idp = self._idps.get(idp_id)
            if not idp or not idp.enabled:
                return {"ok": False, "error": "idp not found or disabled"}
            provider = self.get_provider(idp_id)
            if not isinstance(provider, OIDCProvider):
                return {"ok": False, "error": "unsupported provider type for code flow"}
            # 1) code → token
            token_resp = provider.exchange_code(code, redirect_uri)
            if not token_resp.get("ok"):
                return token_resp
            # 2) 验证 id_token
            verify = provider.verify_id_token(token_resp["id_token"])
            if not verify.get("ok"):
                return verify
            email = verify["email"]
            # 3) 自动 provisioning
            user_id = verify["sub"]
            if idp.auto_provision:
                self._scim.upsert_user(
                    user_name=email,
                    display_name=verify.get("name", ""),
                    active=True,
                    groups=verify.get("groups", []),
                )
            # 4) 创建会话
            sess = self._session_store.create(
                user_id=user_id,
                email=email,
                tenant_id=tenant_id,
                idp_id=idp_id,
                provider_type=idp.type,
                access_token=token_resp["access_token"],
                refresh_token=token_resp["refresh_token"],
                id_token=token_resp["id_token"],
                expires_in=token_resp["expires_in"],
                ip=ip,
                user_agent=user_agent,
            )
            return {
                "ok": True,
                "session_id": sess.id,
                "user_id": user_id,
                "email": email,
                "tenant_id": tenant_id,
                "expires_at": sess.expires_at,
            }

    def logout(self, session_id: str) -> bool:
        return self._session_store.revoke(session_id)

    # ---------- SCIM ----------
    @property
    def scim(self) -> SCIMProvisioner:
        return self._scim

    @property
    def sessions(self) -> SessionStore:
        return self._session_store

    # ---------- 持久化 ----------
    def _write_idp(self, idp: IdentityProvider) -> None:
        if not self._persist_path:
            return
        try:
            with self._persist_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"type": "idp", "data": idp.to_dict()}, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def _load_from_disk(self) -> None:
        if not self._persist_path or not self._persist_path.exists():
            return
        try:
            with self._persist_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if rec.get("type") == "idp":
                        idp = IdentityProvider.from_dict(rec["data"])
                        self._idps[idp.id] = idp
        except Exception:
            pass


# ============================================================================
# 全局单例
# ============================================================================

_GLOBAL_ENGINE: SSOEngine | None = None
_GLOBAL_LOCK = threading.Lock()


def get_sso_engine(persist_path: Path | None = None) -> SSOEngine:
    global _GLOBAL_ENGINE
    with _GLOBAL_LOCK:
        if _GLOBAL_ENGINE is None:
            _GLOBAL_ENGINE = SSOEngine(persist_path=persist_path)
        return _GLOBAL_ENGINE


def reset_sso_engine() -> None:
    global _GLOBAL_ENGINE
    with _GLOBAL_LOCK:
        _GLOBAL_ENGINE = None
