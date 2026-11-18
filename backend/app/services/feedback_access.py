"""Authorization predicates for feedback recipients."""

from sqlalchemy import and_, or_, select

from ..models import TeacherAssignment, User
from ..models.organization import Classroom


def eligible_user_target_clause(sender: User):
    """Select only user recipients this sender may address."""
    allowed_roles = {
        "admin": {"admin", "gestor", "professor", "aluno"},
        "gestor": {"gestor", "professor", "aluno"},
        "professor": {"gestor", "aluno"},
        "aluno": {"gestor", "professor"},
    }
    roles = allowed_roles.get(sender.role, set())
    clause = and_(User.id != sender.id, User.role.in_(roles))
    if sender.role == "admin":
        return clause
    if not sender.school_id:
        return and_(clause, False)
    clause = and_(clause, User.school_id == sender.school_id)
    if sender.role == "professor":
        assigned = (
            select(TeacherAssignment.classroom_id)
            .join(Classroom, Classroom.id == TeacherAssignment.classroom_id)
            .where(TeacherAssignment.teacher_id == sender.id, Classroom.school_id == sender.school_id)
        )
        clause = and_(clause, or_(User.role == "gestor", User.classroom_id.in_(assigned)))
    elif sender.role == "aluno":
        assigned = (
            select(TeacherAssignment.teacher_id)
            .join(Classroom, Classroom.id == TeacherAssignment.classroom_id)
            .where(TeacherAssignment.classroom_id == sender.classroom_id, Classroom.school_id == sender.school_id)
        )
        clause = and_(clause, or_(User.role == "gestor", User.id.in_(assigned)))
    return clause

