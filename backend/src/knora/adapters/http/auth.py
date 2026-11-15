from typing import Annotated

from fastapi import APIRouter, Depends, Header, Response
from pydantic import BaseModel

from knora.access.identity import BearerIdentityAuthenticator
from knora.adapters.http.routes import get_authenticator
from knora.domain.errors import KnoraError

router = APIRouter(prefix="/v1/auth", tags=["auth"])


class AuthSessionResponse(BaseModel):
    issuer: str
    subject: str
    capabilities: list[str]
    session_id: str | None = None


@router.get("/session", response_model=AuthSessionResponse)
def get_auth_session(
    response: Response,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    authenticator=Depends(get_authenticator),  # noqa: B008
) -> AuthSessionResponse:
    response.headers["Cache-Control"] = "no-store"
    if not isinstance(authenticator, BearerIdentityAuthenticator):
        raise KnoraError("UNAUTHENTICATED")
    identity = authenticator.authenticate_identity(authorization)

    session_id: str | None = None
    if hasattr(authenticator, "_claims_from_header"):
        try:
            claims = authenticator._claims_from_header(authorization)
            raw_sid = claims.get("session_id")
            if isinstance(raw_sid, str):
                session_id = raw_sid
        except Exception:
            pass

    return AuthSessionResponse(
        issuer=identity.issuer,
        subject=identity.subject,
        capabilities=list(identity.capabilities),
        session_id=session_id,
    )
