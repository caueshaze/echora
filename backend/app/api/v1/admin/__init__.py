"""Administrative API router composed from domain-specific modules."""

from fastapi import APIRouter, Depends

from . import assignments, classrooms, metrics, schools, subjects, triggers, users, reveals
from .idempotency import administrative_idempotency

router = APIRouter(prefix="/admin", tags=["admin"])

for module in (
    metrics,
    triggers,
    schools,
    subjects,
    classrooms,
    users,
    assignments,
    reveals,
):
    router.include_router(module.router, dependencies=[Depends(administrative_idempotency)])
