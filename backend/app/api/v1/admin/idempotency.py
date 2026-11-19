"""Transaction-bound retry markers for administrative mutations."""
import hashlib
import hmac
from uuid import UUID, uuid4
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from ....core.config import Settings, get_settings
from ....core.database import get_session
from ....core.security import get_current_user
from ....models import AdminOperation
from ....schemas.user import UserPublic


async def administrative_idempotency(request: Request, actor: UserPublic = Depends(get_current_user),
                                     db: Session = Depends(get_session), settings: Settings = Depends(get_settings)) -> None:
    db.info.pop('audit_operation_id', None)
    if request.method not in {'POST', 'PUT', 'PATCH', 'DELETE'}:
        return
    raw_key = request.headers.get('Idempotency-Key')
    if not raw_key:
        raise HTTPException(status_code=400, detail='Idempotency-Key é obrigatório')
    try:
        key = str(UUID(raw_key))
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail='Chave de idempotência inválida') from None
    if request.url.path.endswith('/identity'):
        return
    digest_key = hashlib.sha256(key.encode('ascii')).hexdigest()
    payload = b'\0'.join([request.method.encode(), request.url.path.encode(),
                           request.url.query.encode(), await request.body()])
    fingerprint = hmac.new(settings.secret_key.encode(), payload, hashlib.sha256).hexdigest()
    previous = db.scalar(select(AdminOperation).where(AdminOperation.actor_id == actor.id,
                                                       AdminOperation.key_digest == digest_key))
    if previous:
        if previous.request_digest is None:
            raise HTTPException(status_code=409, detail='Chave de operação já utilizada')
        detail = 'Operação já concluída' if hmac.compare_digest(previous.request_digest, fingerprint) else 'Chave já usada em outra operação'
        raise HTTPException(status_code=409, detail=detail)
    entry = AdminOperation(id=str(uuid4()), actor_id=actor.id, key_digest=digest_key, request_digest=fingerprint)
    db.add(entry)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail='Chave já usada em outra operação ou operação já concluída') from None
    db.info['audit_operation_id'] = entry.id
