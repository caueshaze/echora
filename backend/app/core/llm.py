"""
LLM / Gemma integration for feedback summaries.

Responsabilidades:

- Carregar o modelo Gemma 2B-IT local (somente se habilitado).
- Gerar resumos amigáveis e interpretativos em PT-BR a partir de feedbacks.
- NÃO fazer fallback heurístico:
    - Se o LLM não estiver configurado/corretamente carregado -> RuntimeError.

Funções principais usadas pelas rotas:
- generate_personal_summary(db, current_user)
- generate_admin_summary(db, school_id=None)
"""

from __future__ import annotations

import logging
import os
import re
from time import perf_counter
from threading import BoundedSemaphore
from typing import Iterable, Sequence, List, Optional

import httpx

from fastapi import HTTPException
from sqlalchemy import String, and_, cast, desc, exists, or_, select
from sqlalchemy.orm import Session

from ..models import Feedback, User
from ..models.organization import Classroom, Subject
from ..services.access_control import resolve_school_assignment
from ..schemas.summary import FeedbackSummary
from ..schemas.user import UserPublic
from .config import get_settings
from .crypto import decrypt_feedback

LOGGER = logging.getLogger(__name__)

# Tentamos importar libs necessárias — se faltar, falha só em runtime
try:
    from transformers import AutoTokenizer, AutoModelForCausalLM  # type: ignore
    import torch  # type: ignore
except Exception:  # pragma: no cover
    AutoTokenizer = None  # type: ignore
    AutoModelForCausalLM = None  # type: ignore
    torch = None  # type: ignore

_LLM_MODEL = None
_LLM_TOKENIZER = None
_LLM_READY = False
_SUMMARY_SLOTS = BoundedSemaphore(5)


# ==========================================================
# Carregamento do Gemma 2B-IT
# ==========================================================
def _ensure_gemma() -> None:
    """Garante que o modelo Gemma está carregado e pronto para uso."""
    global _LLM_MODEL, _LLM_TOKENIZER, _LLM_READY

    if _LLM_READY:
        if _LLM_MODEL is None or _LLM_TOKENIZER is None:
            raise RuntimeError("LLM marcado como pronto, mas modelo/tokenizer ausentes.")
        return

    settings = get_settings()

    provider = (getattr(settings, "llm_provider", "gemma") or "gemma").lower()
    gemma_enabled = bool(getattr(settings, "gemma_enabled", False))

    if not gemma_enabled:
        raise RuntimeError("Gemma LLM desabilitado via configuração (GEMMA_ENABLED=false).")

    if provider not in ("gemma", "auto"):
        raise RuntimeError(f"LLM_PROVIDER={settings.llm_provider} não suportado por este módulo Gemma.")

    if AutoTokenizer is None or AutoModelForCausalLM is None or torch is None:
        raise RuntimeError("Gemma requer 'transformers' e 'torch' instalados.")

    model_dir = getattr(settings, "gemma_model_dir", None)
    if not model_dir:
        raise RuntimeError("Faltando GEMMA_MODEL_DIR / gemma_model_dir na configuração.")

    try:
        LOGGER.info("Carregando Gemma 2B-IT de %s ...", model_dir)

        tokenizer = AutoTokenizer.from_pretrained(
            model_dir,
            local_files_only=True,
        )

        # 2B roda tranquilo em float16 em GPU ou float32 em CPU
        dtype = torch.float16 if torch.cuda.is_available() else torch.float32

        model = AutoModelForCausalLM.from_pretrained(
            model_dir,
            local_files_only=True,
            torch_dtype=dtype,
            device_map="auto" if torch.cuda.is_available() else None,
        )

        model.eval()

        _LLM_TOKENIZER = tokenizer
        _LLM_MODEL = model
        _LLM_READY = True

        LOGGER.info("✅ Gemma 2B-IT carregado com sucesso de %s", model_dir)

    except Exception as exc:  # pragma: no cover
        _LLM_MODEL = None
        _LLM_TOKENIZER = None
        _LLM_READY = False
        LOGGER.exception("Falha ao carregar modelo Gemma: %s", exc)
        raise RuntimeError(f"Failed to load Gemma model: {exc}")


# ==========================================================
# Pós-processamento mínimo
# ==========================================================
def _post_process_summary(text: str) -> str:
    """Limpa ecos óbvios de prompt/meta e suaviza extremos, mantendo o máximo possível do que o modelo escreveu."""

    if not text:
        return ""

    # Remove cabeçalhos de template tipo "Instruction:", "Response:", etc.
    cleaned_lines: List[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        lower = stripped.lower()

        if not stripped:
            cleaned_lines.append("")
            continue

        if lower.startswith("### instruction") or lower.startswith("### input") or lower.startswith("### response"):
            continue
        if lower in ("instruction:", "input:", "response:"):
            continue

        if lower.startswith("não inclua") or lower.startswith("nao inclua"):
            continue
        if lower.startswith("não adicione") or lower.startswith("nao adicione"):
            continue

        cleaned_lines.append(line)

    text = "\n".join(cleaned_lines).strip()

    # Remove prefixos tipo "assistant:" / "model:" / "gemma:"
    text = re.sub(
        r"^(assistant|model|gemma)[:\-\s]+",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()

    # Remove ênfases globais se só envolverem tudo
    if text.startswith("**") and text.endswith("**") and "\n" not in text:
        text = text.strip("*").strip()
    if text.startswith("*") and text.endswith("*") and "\n" not in text:
        text = text.strip("*").strip()

    # Normaliza quebras de linha múltiplas
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    # Suaviza agressões literais mais pesadas
    banned = [
        r"\berrou tudo\b",
        r"\bhorrível\b",
        r"\bhorrivel\b",
        r"\bpéssimo\b",
        r"\bpessimo\b",
    ]
    for pattern in banned:
        text = re.sub(
            pattern,
            "teve momentos desafiadores",
            text,
            flags=re.IGNORECASE,
        )

    # Remove meta muito explícita / ofício
    meta_phrases = [
        "Deixo um comentário sobre",
        "Segue um comentário sobre",
        "seguem algumas observações",
        "a seguir algumas observações",
        "espero que isso seja útil",
        "Atenciosamente,",
    ]
    for frag in meta_phrases:
        text = text.replace(frag, "")

    # Remove assinatura "Maya" no final, se vier
    text = re.sub(r"[\n\r\s,\-–]*Maya\s*$", "", text).strip()

    # Arruma "Olá X,\n\n" em "Olá X, " para ficar mais fluido
    text = re.sub(
        r"^Olá\s+([A-Za-zÀ-ÿ]+),\s*\n+\s*",
        r"Olá \1, ",
        text,
    )

    # Corrige incoerência de gênero básica ("ela" -> "você") quando usado solto
    # (bem simples, pra não travar geral)
    text = re.sub(r"\bela\b", "você", text, flags=re.IGNORECASE)

    # Não enforcar o texto: só se tiver parágrafo demais, reduz a ruído
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    if len(paragraphs) > 3:
        text = "\n\n".join(paragraphs[:3])

    return text.strip()


def measure_llm_latency(prompt_text: str = "Gere um breve resumo positivo.", max_new_tokens: int = 64) -> float | None:
    """
    Executa uma inferência curta no Gemma e retorna o tempo em milissegundos.
    Retorna None quando o LLM não estiver habilitado ou ocorrer falha durante a geração.
    """
    start = perf_counter()
    try:
        _run_llm(prompt_text, max_new_tokens=max_new_tokens)
    except Exception as exc:  # pragma: no cover - depende do ambiente
        LOGGER.info("Não foi possível medir latência do Gemma: %s", exc)
        return None
    return (perf_counter() - start) * 1000

# ==========================================================
# Execução do Modelo de Linguagem (OpenAI / Gemma)
# ==========================================================
def _run_openai(prompt_text: str, max_new_tokens: int = 500) -> str:
    """Executa a geração do resumo via API da OpenAI ou compatível."""
    settings = get_settings()
    api_key = settings.openai_api_key or os.getenv("OPENAI_API_KEY", "").strip()

    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY não configurada. Defina OPENAI_API_KEY no arquivo .env."
        )

    base_url = (settings.openai_api_base or "https://api.openai.com/v1").rstrip("/")
    endpoint = f"{base_url}/chat/completions"
    settings.validate_integration_url("OPENAI_API_BASE", endpoint)
    model = settings.summary_model or "gpt-5-nano"

    LOGGER.info("Enviando solicitação de resumo à OpenAI (modelo: %s, endpoint: %s)", model, endpoint)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Você é Maya, uma mentora empática, acolhedora e otimista da plataforma educacional Echora. "
                    "Sua missão é sintetizar os feedbacks escolares de forma construtiva, amigável e direta em português do Brasil."
                ),
            },
            {"role": "user", "content": prompt_text},
        ],
        "max_completion_tokens": max_new_tokens,
        "store": False,
    }

    try:
        with httpx.Client(timeout=45.0, follow_redirects=False) as client:
            resp = client.post(endpoint, headers=headers, json=payload)
            if resp.status_code != 200:
                LOGGER.error("Erro na resposta da OpenAI (%s)", resp.status_code)
                raise RuntimeError(f"Erro na API da OpenAI ({resp.status_code})")
            data = resp.json()
            raw_text = data["choices"][0]["message"]["content"].strip()
            return _post_process_summary(raw_text)
    except httpx.HTTPError as exc:
        LOGGER.exception("Falha de conexão com a OpenAI: %s", exc)
        raise RuntimeError(f"Falha de conexão com a OpenAI: {exc}") from exc


def _run_llm(prompt_text: str, max_new_tokens: int = 260) -> str:
    """
    Executa o LLM configurado (OpenAI ou Gemma local) para gerar a mensagem de feedback.
    """
    settings = get_settings()
    provider = (
        getattr(settings, "summary_provider", None)
        or getattr(settings, "llm_provider", None)
        or "openai"
    ).lower()

    if provider in ("openai", "chatgpt"):
        return _run_openai(prompt_text, max_new_tokens=max_new_tokens)

    _ensure_gemma()
    assert _LLM_MODEL is not None
    assert _LLM_TOKENIZER is not None

    inputs = _LLM_TOKENIZER(
        prompt_text,
        return_tensors="pt",
        truncation=True,
        max_length=2048,
    )

    # Envia para o mesmo device do modelo
    if torch.cuda.is_available():
        try:
            device = next(_LLM_MODEL.parameters()).device  # type: ignore[attr-defined]
            inputs = {k: v.to(device) for k, v in inputs.items()}
        except Exception:
            inputs = {k: v.to("cuda") for k, v in inputs.items()}

    input_ids = inputs["input_ids"]
    prompt_len = input_ids.size(1)

    with torch.no_grad():
        output_ids = _LLM_MODEL.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=True,
            temperature=0.7,
            top_p=0.9,
            pad_token_id=_LLM_TOKENIZER.eos_token_id,
        )

    if output_ids.size(1) <= prompt_len:
        raise RuntimeError("Gemma não gerou tokens novos (EOS imediato).")

    gen_ids = output_ids[0, prompt_len:]
    raw = _LLM_TOKENIZER.decode(gen_ids, skip_special_tokens=True).strip()

    text = _post_process_summary(raw)

    if not text or len(text.split()) < 15:
        raise RuntimeError("Resumo inválido ou muito curto gerado pelo LLM")

    return text


# ==========================================================
# Utilitários para leitura e agrupamento
# ==========================================================
def _fetch_feedbacks(
    db: Session,
    where_clause=None,
    limit: int = 50,
) -> Sequence[Feedback]:
    query = select(Feedback).order_by(desc(Feedback.created_at)).limit(limit)
    if where_clause is not None:
        query = query.where(where_clause)
    return db.execute(query).scalars().all()


def _decrypt_and_bucket(
    feedbacks: Iterable[Feedback],
) -> tuple[List[str], List[str], List[str]]:
    positives: List[str] = []
    negatives: List[str] = []
    neutrals: List[str] = []

    for fb in feedbacks:
        text = decrypt_feedback(fb)

        label = (fb.sentiment_label or "").lower()
        if label.startswith("pos"):
            positives.append(text)
        elif label.startswith("neg"):
            negatives.append(text)
        else:
            neutrals.append(text)

    return positives, negatives, neutrals


# ==========================================================
# Construção do prompt-base (Gemma-friendly)
# ==========================================================
def _build_prompt(
    recipient_name: str,
    positives: List[str],
    negatives: List[str],
    neutrals: List[str],
    audience: str = "aluno",
) -> str:
    """
    Monta o prompt para Gemma gerar uma mensagem curta, acolhedora e construtiva,
    adaptando o tom conforme o tipo de destinatário:
    - aluno / responsável / usuário
    - professor
    - gestor (visão da unidade / instituição)
    """

    def fmt_feedback_items(items: List[str], max_len: int = 160) -> str:
        cleaned: List[str] = []
        for item in items:
            item = " ".join(item.strip().split())
            if not item:
                continue
            if len(item) > max_len:
                item = item[: max_len - 3] + "..."
            cleaned.append(f"- {item}")
        return "\n".join(cleaned) if cleaned else "- (sem pontos específicos)"

    positives_block = fmt_feedback_items(positives)
    negatives_block = fmt_feedback_items(negatives)
    neutrals_block = fmt_feedback_items(neutrals)

    audience = (audience or "aluno").lower()
    is_professor = audience == "professor"
    is_gestor = audience == "gestor"

    if is_professor:
        # Tom para professores: respeitoso, de igual pra igual, sem paternalismo
        intro = (
            f"Você é Maya, uma mentora externa, empática e otimista, que conversa de forma simples, direta e de igual para igual.\n"
            f"Com base nos feedbacks abaixo sobre {recipient_name}, escreva uma mensagem curta e respeitosa diretamente para essa pessoa.\n\n"
            "Siga estas ideias:\n"
            "- Reconheça o esforço, a entrega e o impacto positivo quando aparecerem.\n"
            "- Se houver críticas, transforme em oportunidades de ajuste de práticas, não ataques pessoais.\n"
            "- Fale de profissional para profissional, em tom de parceria, não de cobrança ou superioridade.\n"
            "- Evite palavras como 'péssima', 'confusa', 'ruim', 'problema', 'preocupante'. Prefira 'desafiadora', 'poderia ser mais clara', 'ainda em ajuste'.\n"
            "- Linguagem humana, sem burocracia, sem parecer comunicado oficial.\n"
            "- A mensagem deve ter até dois parágrafos curtos (4–6 frases no total).\n"
            "- Não use listas, títulos, nem assinatura.\n\n"
        )

    elif is_gestor:
        # Tom para gestor: visão macro, estratégica, colaborativa, sem ataque e sem bajulação
        intro = (
            f"Você é Maya, uma mentora externa, empática e objetiva, que ajuda a transformar feedbacks em visão estratégica.\n"
            f"Com base nos feedbacks abaixo sobre {recipient_name}, escreva uma mensagem curta direcionada ao gestor responsável.\n\n"
            "Siga estas ideias:\n"
            "- Traga uma visão geral do clima, pontos fortes e oportunidades de melhoria da unidade/instituição.\n"
            "- Use linguagem clara e profissional, mas acolhedora; nada de tom ameaçador ou punitivo.\n"
            "- Destaque o que já funciona bem (relacionamento, comunicação, práticas positivas) e 1–2 frentes onde ajustes podem gerar impacto.\n"
            "- Evite culpabilizar indivíduos ou usar termos como 'fracasso', 'grave', 'inaceitável'. Fale em 'sinais', 'pistas', 'espaços de ajuste'.\n"
            "- A mensagem deve ter até dois parágrafos curtos (4–6 frases no total), sem listas, relatórios técnicos ou jargão pesado.\n"
            "- Não explique o processo, não assine, não use 'como consultoria', apenas a mensagem final.\n\n"
        )

    else:
        # Tom padrão (aluno / responsável / outros)
        intro = (
            f"Você é Maya, uma mentora externa, empática e otimista, que conversa de forma simples e próxima.\n"
            f"Com base nos feedbacks abaixo sobre {recipient_name}, escreva uma mensagem curta diretamente para essa pessoa.\n\n"
            "Siga estas ideias:\n"
            "- Use o que os feedbacks indicam: pontos fortes, desafios e oportunidades de ajuste.\n"
            "- Reconheça o potencial e os avanços; trate os pontos difíceis como chance de organizar melhor o caminho.\n"
            "- Use tom acolhedor e honesto, sem dramatizar e sem soar como comunicado oficial.\n"
            "- A mensagem deve ter no máximo dois parágrafos curtos (4–6 frases no total).\n"
            "- Não use listas, não explique que está analisando feedbacks, não assine formalmente.\n\n"
        )

    user_content = (
        intro
        + f"Feedbacks positivos sobre {recipient_name}:\n{positives_block}\n\n"
        + f"Pontos de atenção / desenvolvimento:\n{negatives_block}\n\n"
        + f"Observações neutras / contexto:\n{neutrals_block}\n\n"
        + "Agora escreva APENAS a mensagem final de Maya para essa pessoa, seguindo essas diretrizes."
    )

    tokenizer = _LLM_TOKENIZER

    # Usa chat_template se disponível (apenas role 'user' para Gemma)
    if tokenizer is not None and hasattr(tokenizer, "apply_chat_template"):
        try:
            messages = [
                {
                    "role": "user",
                    "content": user_content,
                }
            ]
            prompt = tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
            )
            return prompt
        except Exception as exc:
            LOGGER.warning(
                "Falha ao aplicar chat_template do Gemma (%s). Usando prompt plano.",
                exc,
            )

    # Fallback: prompt plano
    prompt = user_content + "\n\nResposta:"
    return prompt

# ==========================================================
# Sumário e integração com as rotas
# ==========================================================
def _redact_personal_data(text: str, known_name: str = "") -> str:
    """Remove common direct identifiers; free text can still identify people."""
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[e-mail removido]", text)
    text = re.sub(r"(?<!\w)(?:\+?\d[\d .()/-]{8,}\d)(?!\w)", "[número removido]", text)
    if len(known_name.strip()) >= 3:
        text = re.sub(re.escape(known_name.strip()), "[nome removido]", text, flags=re.IGNORECASE)
    return text


def _summarize_feedbacks(
    db: Session,
    where_clause,
    subject: str,
    audience: str,
    limit: int = 50,
) -> FeedbackSummary:
    feedbacks = list(_fetch_feedbacks(db, where_clause=where_clause, limit=limit))
    if not feedbacks:
        raise RuntimeError(f"Nenhum feedback disponível para {subject}.")

    positives, negatives, neutrals = _decrypt_and_bucket(feedbacks)
    total = len(feedbacks)

    LOGGER.info(
        "Gerando resumo LLM (Gemma) para '%s' (%s): %d feedbacks (pos=%d, neg=%d, neutro=%d)",
        "destinatário",
        audience,
        total,
        len(positives),
        len(negatives),
        len(neutrals),
    )

    prompt = _build_prompt(
        recipient_name={"professor": "docente", "aluno": "estudante", "gestor": "unidade escolar"}.get(audience, "pessoa"),
        positives=[_redact_personal_data(value, subject) for value in positives],
        negatives=[_redact_personal_data(value, subject) for value in negatives],
        neutrals=[_redact_personal_data(value, subject) for value in neutrals],
        audience=audience,
    )

    if not _SUMMARY_SLOTS.acquire(blocking=False):
        raise HTTPException(status_code=503, detail="Limite de resumos simultâneos atingido; tente novamente")
    try:
        summary_text = _run_llm(prompt, max_new_tokens=768)
    finally:
        _SUMMARY_SLOTS.release()

    return FeedbackSummary(
        summary_text=summary_text,
        positives=positives[:3],
        opportunities=negatives[:3],
        gemma_ready=True,  # legado
    )


def generate_personal_summary(
    db: Session,
    current_user: UserPublic,
) -> FeedbackSummary:
    user_id = str(current_user.id)
    subject = current_user.full_name or current_user.email or "você"
    role = (getattr(current_user, "role", "") or "usuário").lower()

    if role == "aluno":
        audience = "aluno"
    elif role == "professor":
        audience = "professor"
    else:
        audience = "usuário"

    where_clause = (Feedback.target_id == user_id)
    return _summarize_feedbacks(db, where_clause, subject, audience)


def generate_admin_summary(
    db: Session,
    current_user: UserPublic,
    school_id: Optional[int] = None,
) -> FeedbackSummary:
    if current_user.role not in ("admin", "gestor"):
        raise HTTPException(status_code=403, detail="Perfil sem permissão para acessar resumos")
    school_id = resolve_school_assignment(current_user, school_id)
    if school_id is None or isinstance(school_id, bool) or not isinstance(school_id, int) or school_id <= 0:
        raise HTTPException(status_code=400, detail="Selecione uma unidade escolar para gerar o resumo")
    subject = f"a unidade {school_id}"
    audience = "gestor"
    # Both ends must belong to the selected school. Unknown/deleted targets and
    # cross-school feedbacks are excluded rather than assigned speculatively.
    sender_in_school = exists(select(User.id).where(User.id == Feedback.sender_id, User.school_id == school_id))
    target_in_school = or_(
        and_(Feedback.target_type == "user", exists(select(User.id).where(User.id == Feedback.target_id, User.school_id == school_id))),
        and_(Feedback.target_type == "subject", exists(select(Subject.id).where(cast(Subject.id, String) == Feedback.target_id, Subject.school_id == school_id))),
        and_(Feedback.target_type == "class", exists(select(Classroom.id).where(cast(Classroom.id, String) == Feedback.target_id, Classroom.school_id == school_id))),
    )
    where_clause = and_(sender_in_school, target_in_school)
    return _summarize_feedbacks(db, where_clause, subject, audience)
