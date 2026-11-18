"""Sentiment prediction endpoints."""

import logging
from typing import Any, List, Optional
from pathlib import Path

import joblib
from fastapi import APIRouter, Depends, HTTPException, Response, status

from ...core.config import PROJECT_ROOT, Settings, get_settings
from ...core.security import require_role
from ...core.text import build_context_text
from ...schemas import (
    PredictBatchRequest,
    PredictBatchResponse,
    PredictBatchResponseItem,
    PredictItem,
    PredictResponse,
)

router = APIRouter(prefix="/predict", tags=["predict"])
LOGGER = logging.getLogger(__name__)

_model: Optional[Any] = None


def load_model(settings: Settings) -> Any:
    """Load the ML model from disk (cached)."""
    global _model
    if _model is None:
        try:
            configured_path = Path(settings.model_path)
            if not configured_path.is_absolute():
                configured_path = PROJECT_ROOT / configured_path
            model_path = configured_path.resolve()
            trusted_models_dir = (PROJECT_ROOT / "models").resolve()
            if model_path.suffix.lower() != ".joblib":
                raise ValueError("O modelo legado deve ser um arquivo .joblib")
            try:
                model_path.relative_to(trusted_models_dir)
            except ValueError:
                raise ValueError("O modelo legado deve estar dentro da pasta local models") from None
            _model = joblib.load(str(model_path))
        except Exception as exc:
            LOGGER.exception("Falha ao carregar modelo legado joblib")
            raise RuntimeError(
                "Não foi possível carregar o modelo legado"
            ) from exc
    return _model


@router.get("/health", summary="Verifica a disponibilidade da API",
            dependencies=[Depends(require_role("professor", "gestor", "admin"))])
def health(response: Response) -> dict:
    response.headers["Cache-Control"] = "no-store"
    # Passive: the legacy joblib model is loaded only by prediction requests.
    return {"status": "ok"}


@router.get("/version", summary="Retorna a versão da API",
            dependencies=[Depends(require_role("admin"))])
def version(response: Response, settings: Settings = Depends(get_settings)) -> dict:
    response.headers["Cache-Control"] = "no-store"
    return {"api_version": settings.api_version}


@router.post(
    "/predict",
    response_model=PredictResponse,
    dependencies=[Depends(require_role("professor", "gestor", "admin", "aluno"))],
    summary="Prevê o sentimento de um único texto",
)
def predict(
    item: PredictItem,
    settings: Settings = Depends(get_settings),
) -> PredictResponse:
    try:
        model = load_model(settings)
        text_ctx = build_context_text(
            texto=item.texto,
            author_role=item.author_role,
            target_type=item.target_type,
            course_code=item.course_code,
        )

        text_list = [text_ctx]
        label = model.predict(text_list)[0]

        conf = None
        if hasattr(model, "predict_proba"):
            probabilities = model.predict_proba(text_list)[0]
            conf = float(max(probabilities))

        return PredictResponse(label=str(label), confidence=conf)
    except Exception:
        LOGGER.exception("Falha interna na predição individual")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Não foi possível concluir a predição.",
        ) from None


@router.post(
    "/predict_batch",
    response_model=PredictBatchResponse,
    dependencies=[Depends(require_role("gestor", "admin"))],
    summary="Prevê o sentimento de múltiplos textos",
)
def predict_batch(
    payload: PredictBatchRequest,
    settings: Settings = Depends(get_settings),
) -> PredictBatchResponse:
    try:
        model = load_model(settings)
        texts: List[str] = [
            build_context_text(
                texto=item.texto,
                author_role=item.author_role,
                target_type=item.target_type,
                course_code=item.course_code,
            )
            for item in payload.items
        ]
        labels = model.predict(texts)

        confs = None
        if hasattr(model, "predict_proba"):
            confs = model.predict_proba(texts).max(axis=1)

        results = [
            PredictBatchResponseItem(
                index=idx,
                label=str(lab),
                confidence=float(confs[idx]) if confs is not None else None,
            )
            for idx, lab in enumerate(labels)
        ]
        return PredictBatchResponse(results=results)
    except Exception:
        LOGGER.exception("Falha interna na predição em lote")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Não foi possível concluir a predição em lote.",
        ) from None
