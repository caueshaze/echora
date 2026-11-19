"""Record denied administrative attempts independently of request transaction."""

import logging
from fastapi import HTTPException, Request
from fastapi.routing import APIRoute
from ....core.database import _get_sessionmaker
from ....services.audit_service import record_event

LOGGER = logging.getLogger(__name__)


class AuditedAdminRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def wrapped(request: Request):
            try:
                return await handler(request)
            except HTTPException as exc:
                actor = getattr(request.state, 'audit_actor', None)
                if exc.status_code in {403, 404} and actor is not None:
                    try:
                        with _get_sessionmaker()() as db:
                            is_reveal = '/reveals' in request.url.path
                            record_event(db, actor=actor, action='reveal.denied' if is_reveal else 'admin.denied',
                                         resource_type='reveal_request' if is_reveal else 'admin', resource_id=None,
                                         school_id=actor.school_id, result='denied')
                            db.commit()
                    except Exception:
                        LOGGER.exception('Falha ao registrar tentativa administrativa negada')
                raise
        return wrapped
