"""Explicit, transactional academic demo dataset; never invoked by the application."""
from __future__ import annotations

import argparse
import getpass
import json
import os
import secrets
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import and_, delete, func, or_, select, text
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from backend.app.core.crypto import encrypt_feedback
from backend.app.core.security import hash_password, verify_password
from backend.app.core.sentiment import get_sentiment_analyzer
from backend.app.core.triggers import detect_triggers, load_trigger_keywords
from backend.app.models import Feedback, User, School, Classroom, Subject, TeacherAssignment
from backend.app.models.organization import classroom_subjects_table, teacher_subjects_table
from backend.app.models.auth_session import AuthSession
from backend.app.models.reveal import RevealPermission, RevealRequest
from backend.app.models.idempotency import AdminOperation
from backend.app.schemas.user import UserPublic, UserCreate
from backend.app.services.audit_service import record_event
from backend.app.services.feedback_access import eligible_user_target_clause
from backend.app.services.assignment_service import _validate_assignment
from backend.app.schemas.assignment import AssignmentEntry

MARKER = 'ECHORA-DEMO-HORIZONTE-V1'
NAMESPACE = uuid.UUID('675643a4-e3f7-4c40-9469-f9360358ddbf')
SCHOOL_ID = 1876000001
CLASS_IDS = list(range(1876000010, 1876000014))
SUBJECT_IDS = list(range(1876000020, 1876000028))
ASSIGNMENT_IDS = list(range(1876000100, 1876000132))
FEEDBACK_IDS = list(range(1876000200, 1876000380))
SUBJECTS = ('Língua Portuguesa', 'Matemática', 'Ciências', 'História', 'Geografia', 'Artes', 'Inglês', 'Educação Física')
FIRST = ('Ana', 'Bruno', 'Caio', 'Débora', 'Eduarda', 'Felipe', 'Gabriela', 'Henrique', 'Isabela', 'João', 'Karen', 'Lucas', 'Marina', 'Nicolas', 'Olívia')
LAST = ('Almeida', 'Barbosa', 'Campos', 'Duarte')
POS = ('As explicações ajudaram a entender o conteúdo', 'Os exemplos tornaram a aula mais clara', 'Gostei do espaço para fazer perguntas', 'As atividades em grupo facilitaram a aprendizagem', 'A devolutiva mostrou onde posso melhorar', 'O ritmo da aula favoreceu minha participação', 'Os exercícios aproximaram a teoria da prática', 'A organização das atividades me ajudou bastante')
NEG = ('O ritmo das explicações ficou rápido demais', 'Faltaram exemplos antes dos exercícios', 'O barulho na sala dificultou a concentração', 'Não consegui esclarecer minhas dúvidas durante a aula', 'O prazo para a atividade pareceu curto', 'A sala ficou quente durante as aulas', 'A conexão da escola interrompeu a atividade', 'Seria útil receber orientações mais claras para a tarefa')
NEU = ('A atividade aconteceu em grupos pequenos', 'Usamos o livro e depois conversamos sobre o tema', 'A turma apresentou os trabalhos nesta semana', 'A avaliação reuniu questões de diferentes assuntos', 'A aula começou com uma revisão do conteúdo', 'A atividade foi realizada em duas etapas')
TAIL = ('na atividade desta semana.', 'durante a revisão do conteúdo.', 'quando fizemos o trabalho em grupo.',
        'no momento de resolver os exercícios.', 'na parte final da aula.', 'na preparação para a avaliação.',
        'quando a turma discutiu o tema.', 'durante a apresentação dos trabalhos.', 'na primeira parte da atividade.',
        'ao longo das últimas aulas.', 'na conversa depois da explicação.', 'ao revisar o material da aula.',
        'enquanto a turma trabalhava em dupla.', 'na correção dos exercícios.', 'ao realizar a tarefa proposta.')
STUDENT_NOTES = ('Você participou das discussões e apresentou ideias relevantes.',
                 'Sua pergunta ajudou a turma a compreender a atividade.',
                 'Você organizou bem as etapas do trabalho em grupo.',
                 'Sua explicação mostrou cuidado com os exemplos estudados.',
                 'Você encontrou uma maneira interessante de resolver o exercício.',
                 'Sua contribuição ajudou o grupo a avançar na tarefa.',
                 'Você demonstrou atenção ao revisar o próprio trabalho.',
                 'Sua participação trouxe uma perspectiva diferente para a discussão.')
STUDENT_TAIL = ('Continue trazendo suas dúvidas para a conversa.', 'Vale registrar essa ideia para retomá-la depois.',
                'Você pode usar essa estratégia em outras atividades.', 'Experimente explicar seu raciocínio também por escrito.',
                'Continue compartilhando suas observações com o grupo.', 'Na próxima atividade, tente comparar outras soluções.',
                'Pode ser interessante revisar os exemplos com a turma.', 'Continue reservando tempo para conferir suas respostas.',
                'Na próxima etapa, procure relacionar essa ideia ao conteúdo.', 'Você pode anotar as perguntas que surgirem durante a leitura.',
                'Vale mostrar os passos que levaram à sua resposta.', 'Continue ouvindo e desenvolvendo as ideias dos colegas.',
                'Experimente testar essa hipótese em outro exemplo.', 'Você pode retomar esse ponto na próxima discussão.',
                'Continue observando como cada etapa contribui para o resultado.')


def uid(kind: str, index: int) -> str:
    return str(uuid.uuid5(NAMESPACE, f'{kind}:{index}'))


def accounts():
    return ([('gestor', 0, 'Gestora Horizonte', None)] +
            [('professor', i, f'Professor {FIRST[i]} {LAST[i % 4]}', None) for i in range(8)] +
            [('aluno', i, f'{FIRST[i % 15]} {LAST[i // 15]}', i // 15) for i in range(60)])


def email(role, index):
    return f'echora-demo-horizonte-{role}-{index:02d}@example.org'


def lock(db):
    if db.bind.dialect.name == 'postgresql':
        db.execute(text("SELECT pg_advisory_xact_lock(1876012026)"))


def _actor(db, actor_id):
    actor = db.get(User, actor_id)
    if not actor or actor.role != 'admin' or actor.school_id is not None:
        raise ValueError('O operador deve informar o ID de um administrador global existente.')
    return UserPublic.model_validate(actor)


def _occupied(db):
    return (db.scalar(select(func.count()).select_from(School).where(or_(School.id == SCHOOL_ID, School.name == 'Escola Horizonte', School.code == MARKER))) or
            db.scalar(select(func.count()).select_from(Classroom).where(Classroom.id.in_(CLASS_IDS))) or
            db.scalar(select(func.count()).select_from(Subject).where(Subject.id.in_(SUBJECT_IDS))) or
            db.scalar(select(func.count()).select_from(TeacherAssignment).where(TeacherAssignment.id.in_(ASSIGNMENT_IDS))) or
            db.scalar(select(func.count()).select_from(Feedback).where(or_(
                Feedback.id.in_(FEEDBACK_IDS),
                and_(Feedback.target_type == 'user', Feedback.target_id.in_([uid(r, i) for r, i, _, _ in accounts()])),
                and_(Feedback.target_type == 'subject', Feedback.target_id.in_([str(i) for i in SUBJECT_IDS])),
                and_(Feedback.target_type == 'class', Feedback.target_id.in_([str(i) for i in CLASS_IDS]))))) or
            db.scalar(select(func.count()).select_from(User).where(or_(User.id.in_([uid(r, i) for r, i, _, _ in accounts()]), User.email.in_([email(r, i) for r, i, _, _ in accounts()])))))


def _verify(db):
    school = db.get(School, SCHOOL_ID)
    if not school or school.name != 'Escola Horizonte' or school.code != MARKER or school.description != MARKER:
        raise ValueError('Marcador da escola ausente ou divergente; operação interrompida.')
    for role, i, _, c in accounts():
        user = db.get(User, uid(role, i))
        if not user or user.email != email(role, i) or user.role != role or user.school_id != SCHOOL_ID or user.classroom_id != (CLASS_IDS[c] if c is not None else None):
            raise ValueError('Conta demonstrativa ausente ou divergente; operação interrompida.')
    for model, ids in ((Classroom, CLASS_IDS), (Subject, SUBJECT_IDS)):
        rows = db.scalars(select(model).where(model.school_id == SCHOOL_ID)).all()
        if {r.id for r in rows} != set(ids) or any(r.code != f'{MARKER}-{r.id}' for r in rows):
            raise ValueError('Dados escolares divergentes ou registros externos associados; operação interrompida.')
    if set(db.scalars(select(User.id).where(User.school_id == SCHOOL_ID))) != {uid(r, i) for r, i, _, _ in accounts()}:
        raise ValueError('Há usuários externos na escola demonstrativa; operação interrompida.')
    assignments = db.scalars(select(TeacherAssignment).where(TeacherAssignment.classroom_id.in_(CLASS_IDS))).all()
    expected = {(ASSIGNMENT_IDS[c * 8 + s], CLASS_IDS[c], SUBJECT_IDS[s], uid('professor', s)) for c in range(4) for s in range(8)}
    if {(a.id, a.classroom_id, a.subject_id, a.teacher_id) for a in assignments} != expected:
        raise ValueError('Atribuições divergentes; operação interrompida.')
    feedbacks = db.scalars(select(Feedback).where(Feedback.id.in_(FEEDBACK_IDS))).all()
    if len(feedbacks) != 180 or any(f.sender_id not in {uid(r, i) for r, i, _, _ in accounts()} for f in feedbacks):
        raise ValueError('Feedbacks demonstrativos divergentes; operação interrompida.')


def _audit(db, actor, action, resource, ident):
    record_event(db, actor=actor, action=action, resource_type=resource, resource_id=ident, school_id=SCHOOL_ID)


def create(db, actor_id, *, fail_after=None):
    lock(db)
    if db.bind.dialect.name == 'postgresql':
        # Feedback targets are polymorphic and lack foreign keys; exclude concurrent
        # references while checking reserved IDs and creating the new institution.
        db.execute(text('LOCK TABLE feedbacks IN SHARE ROW EXCLUSIVE MODE'))
    actor = _actor(db, actor_id)
    if db.get(School, SCHOOL_ID):
        _verify(db)
        return {}, {}
    if _occupied(db):
        raise ValueError('Identificadores ou nome da demonstração já estão em uso; nada foi alterado.')
    db.add(School(id=SCHOOL_ID, name='Escola Horizonte', code=MARKER, description=MARKER))
    db.flush(); _audit(db, actor, 'school.create', 'school', SCHOOL_ID)
    subjects = []
    for i, name in enumerate(SUBJECTS):
        row = Subject(id=SUBJECT_IDS[i], name=name, code=f'{MARKER}-{SUBJECT_IDS[i]}', school_id=SCHOOL_ID)
        db.add(row); subjects.append(row); _audit(db, actor, 'subject.create', 'subject', row.id)
    db.flush()
    classes = []
    for i, ident in enumerate(CLASS_IDS):
        row = Classroom(id=ident, name=f'{7 + i}º ano A', code=f'{MARKER}-{ident}', grade_level=f'{7+i}º ano', school_id=SCHOOL_ID)
        row.subjects = subjects[:]; db.add(row); classes.append(row); _audit(db, actor, 'classroom.create', 'classroom', ident)
    db.flush()
    credentials = {}
    for role, i, name, c in accounts():
        password = secrets.token_urlsafe(24)
        payload = UserCreate(email=email(role, i), full_name=name, role=role, password=password, school_id=SCHOOL_ID,
                             classroom_id=CLASS_IDS[c] if c is not None else None,
                             teachable_subject_ids=[SUBJECT_IDS[i]] if role == 'professor' else None)
        user = User(id=uid(role, i), email=str(payload.email), full_name=payload.full_name, role=role, school_id=SCHOOL_ID,
                    classroom_id=payload.classroom_id, hashed_password=hash_password(password), must_change_password=True)
        if role == 'professor': user.teachable_subjects = [subjects[i]]
        db.add(user); credentials[str(payload.email)] = password
        _audit(db, actor, 'user.create', 'user', user.id)
    db.flush()
    for c in range(4):
        for s in range(8):
            entry = AssignmentEntry(subject_id=SUBJECT_IDS[s], teacher_id=uid('professor', s))
            _validate_assignment(db, classes[c], entry)
            db.add(TeacherAssignment(id=ASSIGNMENT_IDS[c * 8 + s], classroom_id=CLASS_IDS[c], subject_id=SUBJECT_IDS[s], teacher_id=entry.teacher_id))
        _audit(db, actor, 'assignment.update', 'classroom', CLASS_IDS[c])
    db.flush()
    if fail_after == 'accounts': raise RuntimeError('falha simulada')
    keywords = load_trigger_keywords(db, SCHOOL_ID)
    analyzer = get_sentiment_analyzer()  # local ONNX / local fallback only; never calls remote APIs
    now = datetime.now(timezone.utc)
    month_index = now.year * 12 + now.month - 1
    for i, ident in enumerate(FEEDBACK_IDS):
        month, student = divmod(i, 60)
        professor = (student // 4 + student % 4) % 8
        sender = db.get(User, uid('aluno', student))
        if student % 4 == 0:
            sender = db.get(User, uid('professor', professor)); target = uid('aluno', student)
            content = (STUDENT_NOTES[(student // 4 + month) % len(STUDENT_NOTES)] + ' ' +
                       STUDENT_TAIL[student // 4])
        else:
            target = uid('professor', professor) if student % 4 != 1 else uid('gestor', 0)
            if professor == 2 and month == 0: base = NEG[(student // 2) % len(NEG)]
            elif professor == 2 and month == 2: base = POS[(student // 2) % len(POS)]
            elif professor == 3: base = NEG[(student // 2) % len(NEG)]
            elif student % 7 == 0: base = NEU[(student + month) % len(NEU)]
            elif student % 5 == 0: base = POS[(student + month) % len(POS)] + ', mas ' + NEG[(student + month) % len(NEG)].lower()
            else: base = POS[(student + month) % len(POS)]
            content = f'{base} {TAIL[(student // 3 + month) % len(TAIL)]}'
        if not db.scalar(select(User.id).where(User.id == target, eligible_user_target_clause(sender))):
            raise ValueError('Destinatário de feedback incompatível com as permissões existentes.')
        anon = sender.role == 'aluno' and student % 2 == 0
        encrypted, nonce = encrypt_feedback(content, sender_id=sender.id, target_type='user', target_id=target, is_anonymous=anon)
        label, score = analyzer.predict(content)
        date_index = month_index - (2 - month)
        created = datetime(date_index // 12, date_index % 12 + 1, 1 + student % 27, 12, tzinfo=timezone.utc)
        if created > now: created = now
        db.add(Feedback(id=ident, sender_id=sender.id, target_type='user', target_id=target, content_encrypted=encrypted, nonce=nonce,
                        sentiment=label, sentiment_label=label, sentiment_score=score, has_trigger=bool(detect_triggers(content, keywords)), is_anonymous=anon, created_at=created))
    db.flush(); _audit(db, actor, 'demo.seed', 'school', SCHOOL_ID)
    return {'schools': 1, 'subjects': 8, 'classrooms': 4, 'managers': 1, 'teachers': 8, 'students': 60, 'assignments': 32, 'feedbacks': 180}, credentials


def remove(db, actor_id):
    lock(db)
    if db.bind.dialect.name == 'postgresql':
        # Stabilize the reference checks until deletion commits, including polymorphic targets
        # which are not protected by a foreign key.
        db.execute(text('LOCK TABLE schools, classrooms, subjects, users, teacher_assignments, '
                        'classroom_subjects, teacher_subjects, feedbacks, auth_sessions, '
                        'reveal_permissions, reveal_requests, admin_operations, trigger_keywords '
                        'IN SHARE ROW EXCLUSIVE MODE'))
    actor = _actor(db, actor_id)
    _verify(db)
    ids = [uid(r, i) for r, i, _, _ in accounts()]
    # Refuse if anything outside the seed references its entities; never cascade it away.
    external_feedback = db.scalar(select(func.count()).select_from(Feedback).where(
        or_(Feedback.sender_id.in_(ids), and_(Feedback.target_type == 'user', Feedback.target_id.in_(ids)),
            and_(Feedback.target_type == 'subject', Feedback.target_id.in_([str(i) for i in SUBJECT_IDS])),
            and_(Feedback.target_type == 'class', Feedback.target_id.in_([str(i) for i in CLASS_IDS])),
            Feedback.manual_triggered_by.in_(ids), Feedback.trigger_resolved_by.in_(ids)),
        Feedback.id.not_in(FEEDBACK_IDS)))
    external_assignments = db.scalar(select(func.count()).select_from(TeacherAssignment).where(
        or_(TeacherAssignment.teacher_id.in_(ids), TeacherAssignment.classroom_id.in_(CLASS_IDS), TeacherAssignment.subject_id.in_(SUBJECT_IDS)),
        TeacherAssignment.id.not_in(ASSIGNMENT_IDS)))
    external_class_subjects = db.scalar(select(func.count()).select_from(classroom_subjects_table).where(
        or_(and_(classroom_subjects_table.c.classroom_id.in_(CLASS_IDS), classroom_subjects_table.c.subject_id.not_in(SUBJECT_IDS)),
            and_(classroom_subjects_table.c.subject_id.in_(SUBJECT_IDS), classroom_subjects_table.c.classroom_id.not_in(CLASS_IDS)))))
    expected_pairs = {(CLASS_IDS[c], SUBJECT_IDS[s]) for c in range(4) for s in range(8)}
    actual_pairs = set(db.execute(select(classroom_subjects_table.c.classroom_id, classroom_subjects_table.c.subject_id).where(classroom_subjects_table.c.classroom_id.in_(CLASS_IDS))).all())
    teacher_pairs = set(db.execute(select(teacher_subjects_table.c.teacher_id, teacher_subjects_table.c.subject_id).where(
        or_(teacher_subjects_table.c.teacher_id.in_(ids), teacher_subjects_table.c.subject_id.in_(SUBJECT_IDS)))).all())
    expected_teachers = {(uid('professor', i), SUBJECT_IDS[i]) for i in range(8)}
    references = [external_feedback, external_assignments, external_class_subjects,
        db.scalar(select(func.count()).select_from(RevealPermission).where(or_(RevealPermission.user_id.in_(ids), RevealPermission.school_id == SCHOOL_ID))),
        db.scalar(select(func.count()).select_from(RevealRequest).where(or_(RevealRequest.feedback_id.in_(FEEDBACK_IDS), RevealRequest.school_id == SCHOOL_ID, RevealRequest.requester_id.in_(ids), RevealRequest.approver_id.in_(ids)))),
        db.scalar(select(func.count()).select_from(AdminOperation).where(AdminOperation.actor_id.in_(ids))),
        db.scalar(select(func.count()).select_from(User).where(User.classroom_id.in_(CLASS_IDS), User.id.not_in(ids)))]
    if any(references) or actual_pairs != expected_pairs or teacher_pairs != expected_teachers:
        raise ValueError('Há referências externas ou alterações posteriores; remoção cancelada para proteger outros dados.')
    demo_feedbacks = db.scalars(select(Feedback).where(Feedback.id.in_(FEEDBACK_IDS))).all()
    if any(f.target_type != 'user' or f.target_id not in ids for f in demo_feedbacks):
        raise ValueError('Destinos dos feedbacks foram alterados; remoção cancelada.')
    db.execute(delete(Feedback).where(Feedback.id.in_(FEEDBACK_IDS)))
    db.execute(delete(TeacherAssignment).where(TeacherAssignment.id.in_(ASSIGNMENT_IDS)))
    # Sessions belong to the demo accounts and would otherwise cascade when those accounts are deleted.
    session_count = db.execute(delete(AuthSession).where(AuthSession.user_id.in_(ids))).rowcount
    db.execute(delete(teacher_subjects_table).where(teacher_subjects_table.c.teacher_id.in_(ids)))
    db.execute(delete(classroom_subjects_table).where(classroom_subjects_table.c.classroom_id.in_(CLASS_IDS)))
    db.execute(delete(User).where(User.id.in_(ids)))
    db.execute(delete(Classroom).where(Classroom.id.in_(CLASS_IDS)))
    db.execute(delete(Subject).where(Subject.id.in_(SUBJECT_IDS)))
    db.execute(delete(School).where(School.id == SCHOOL_ID))
    _audit(db, actor, 'demo.remove', 'school', SCHOOL_ID)
    return {'schools': 1, 'subjects': 8, 'classrooms': 4, 'users': 69, 'assignments': 32, 'feedbacks': 180, 'sessions': session_count}


def main():
    parser = argparse.ArgumentParser(description='Conjunto acadêmico fictício da Escola Horizonte')
    parser.add_argument('--actor-id', required=True, help='UUID de administrador global existente para auditoria')
    parser.add_argument('--dry-run', action='store_true', help='Apenas verificar conflitos e apresentar quantidades; não cria credenciais')
    parser.add_argument('--remove', action='store_true', help='Remover somente o conjunto demonstrativo íntegro')
    parser.add_argument('--allow-production', action='store_true', help='Reconhecer que o alvo pode ser produção; obrigatório para qualquer alteração')
    parser.add_argument('--credentials-file', help='Arquivo novo e exclusivo para credenciais; obrigatório na criação')
    args = parser.parse_args()
    url = os.environ.get('ECHORA_DEMO_DATABASE_URL')
    if not url: parser.error('Defina ECHORA_DEMO_DATABASE_URL explicitamente em ambiente protegido.')
    if not url.startswith(('postgresql://', 'postgresql+psycopg://')): parser.error('O comando requer PostgreSQL.')
    if not args.dry_run and not args.allow_production: parser.error('Alterações exigem --allow-production e confirmação explícita, independentemente do ambiente.')
    if not args.dry_run and not args.remove and not args.credentials_file: parser.error('Informe --credentials-file para criar as credenciais.')
    if not args.dry_run:
        if not sys.stdin.isatty(): parser.error('A execução requer um terminal interativo.')
        target = make_url(url)
        print(f'Alvo PostgreSQL: {target.host or "socket local"}:{target.port or 5432}/{target.database}')
        action = 'REMOVER' if args.remove else 'CRIAR'
        if input(f'Digite {action} {MARKER} para confirmar: ') != f'{action} {MARKER}': parser.error('Confirmação incorreta.')
        actor_password = getpass.getpass('Senha do administrador informado: ')
    engine = create_engine(url, hide_parameters=True)
    path = Path(args.credentials_file) if args.credentials_file else None
    fd = None
    created_file = False
    committed = False
    try:
        with Session(engine) as db, db.begin():
            if not args.dry_run:
                operator = db.get(User, args.actor_id)
                if not operator or operator.role != 'admin' or operator.school_id is not None or operator.must_change_password or not verify_password(actor_password, operator.hashed_password):
                    raise ValueError('Credenciais do administrador inválidas ou senha pendente de troca.')
            if args.dry_run:
                lock(db); _actor(db, args.actor_id)
                if db.get(School, SCHOOL_ID):
                    _verify(db)
                    report = {'estado': 'já existe', 'removeria' if args.remove else 'criaria': 1 if args.remove else 0}
                elif args.remove: raise ValueError('A escola demonstrativa não existe.')
                elif _occupied(db): raise ValueError('Identificadores ou nome já estão em uso.')
                else: report = {'estado': 'prévia', 'schools': 1, 'subjects': 8, 'classrooms': 4, 'managers': 1, 'teachers': 8, 'students': 60, 'assignments': 32, 'feedbacks': 180}
            elif args.remove:
                report = remove(db, args.actor_id)
            else:
                report, credentials = create(db, args.actor_id)
                if credentials:
                    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
                    created_file = True
                    with os.fdopen(fd, 'w', encoding='utf-8') as out:
                        fd = None
                        json.dump(credentials, out, ensure_ascii=False, indent=2)
                        out.write('\n'); out.flush(); os.fsync(out.fileno())
        committed = True
        print(json.dumps(report, ensure_ascii=False, indent=2))
        if created_file: print('Credenciais criadas em arquivo exclusivo, com permissões 0600; proteja e remova após provisionar.')
    except Exception:
        if fd is not None: os.close(fd)
        if created_file and not committed and path is not None: path.unlink(missing_ok=True)
        raise
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
