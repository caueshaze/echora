"""Authentication endpoints with bounded, revocable sessions."""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ...core.config import Settings, get_settings
from ...core.database import get_session
from ...core.rate_limit import get_rate_limiter, login_rate_limit
from ...core.security import create_access_token, get_current_user, verify_password
from ...models import AuthSession, User
from ...schemas.auth import LoginRequest, TokenResponse
from ...schemas.user import UserPublic

router = APIRouter(prefix='/auth', tags=['auth'])
limiter = get_rate_limiter()
COOKIE = 'echora_refresh'
COOKIE_PATH = '/api/v1/auth'


def _hash_token(value: str) -> str:
    return hashlib.sha256(value.encode('ascii')).hexdigest()


def _check_origin(request: Request, settings: Settings) -> None:
    origin = request.headers.get('origin')
    if origin and origin not in settings.cors_origin_list():
        raise HTTPException(status_code=403, detail='Origem não autorizada')


def _response(user: User, session: AuthSession, refresh: str, settings: Settings) -> JSONResponse:
    now = datetime.now(timezone.utc)
    expires = session.expires_at.replace(tzinfo=timezone.utc) if session.expires_at.tzinfo is None else session.expires_at
    token = create_access_token(subject=user.id, role=user.role, settings=settings,
                                expires_delta=min(timedelta(minutes=settings.access_token_expire_minutes), expires - now),
                                extra_claims={'sid': session.id})
    response = JSONResponse(content=TokenResponse(access_token=token).model_dump())
    response.set_cookie(COOKIE, f'{session.id}.{refresh}', max_age=max(0, int((expires-now).total_seconds())),
                        httponly=True, secure=settings.is_production, samesite='strict', path=COOKIE_PATH)
    response.headers['Cache-Control'] = 'no-store'
    return response


@router.post('/login', response_model=TokenResponse, summary='Realiza login e retorna o token JWT')
@limiter.limit(login_rate_limit())
async def login(request: Request, payload: LoginRequest, settings: Settings = Depends(get_settings), db: Session = Depends(get_session)) -> JSONResponse:
    _check_origin(request, settings)
    user = db.execute(select(User).where(User.email == payload.email.lower())).scalar_one_or_none()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Credenciais inválidas')
    refresh = secrets.token_urlsafe(32)
    session = AuthSession(id=str(uuid4()), user_id=user.id, refresh_hash=_hash_token(refresh),
                          expires_at=datetime.now(timezone.utc) + timedelta(days=settings.session_max_days))
    db.add(session)
    db.commit()
    return _response(user, session, refresh, settings)


@router.get('/me', response_model=UserPublic, summary='Retorna o usuário autenticado')
def read_current_user(current_user: UserPublic = Depends(get_current_user)) -> UserPublic:
    return current_user


def _cookie_parts(request: Request) -> tuple[str, str]:
    value = request.cookies.get(COOKIE, '')
    session_id, separator, secret = value.partition('.')
    if not separator or not session_id or not secret or not secret.isascii() or len(secret) > 128:
        raise HTTPException(status_code=401, detail='Sessão inválida')
    return session_id, secret


@router.post('/refresh', response_model=TokenResponse, summary='Renova a sessão com rotação do refresh token')
@limiter.limit(login_rate_limit())
async def refresh_token(request: Request, settings: Settings = Depends(get_settings), db: Session = Depends(get_session)) -> JSONResponse:
    _check_origin(request, settings)
    session_id, old_token = _cookie_parts(request)
    replacement = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    result = db.execute(update(AuthSession).where(AuthSession.id == session_id, AuthSession.refresh_hash == _hash_token(old_token),
                                                  AuthSession.revoked_at.is_(None), AuthSession.expires_at > now)
                        .values(refresh_hash=_hash_token(replacement)))
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=401, detail='Sessão inválida ou expirada')
    session = db.get(AuthSession, session_id)
    user = db.get(User, session.user_id)
    if not user:
        db.rollback()
        raise HTTPException(status_code=401, detail='Sessão inválida')
    db.commit()
    return _response(user, session, replacement, settings)


@router.post('/logout', status_code=204, summary='Revoga a sessão atual')
def logout(request: Request, settings: Settings = Depends(get_settings), db: Session = Depends(get_session)) -> JSONResponse:
    _check_origin(request, settings)
    session_id, token = _cookie_parts(request)
    db.execute(update(AuthSession).where(AuthSession.id == session_id, AuthSession.refresh_hash == _hash_token(token),
                                         AuthSession.revoked_at.is_(None)).values(revoked_at=datetime.now(timezone.utc)))
    db.commit()
    response = JSONResponse(status_code=204, content=None)
    response.delete_cookie(COOKIE, path=COOKIE_PATH, secure=settings.is_production, httponly=True, samesite='strict')
    return response
