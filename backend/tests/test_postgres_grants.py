"""Privilege checks: ECHORA_TEST_GRANTS_URL must be a disposable echora database."""
import os
from pathlib import Path
import unittest
from uuid import uuid4
from sqlalchemy import create_engine, text


@unittest.skipUnless(os.getenv('ECHORA_TEST_GRANTS_URL'), 'requires an isolated echora database owner URL')
class PostgreSQLGrantsTests(unittest.TestCase):
    def test_explicit_matrix_migrator_ownership_and_future_table(self):
        engine = create_engine(os.environ['ECHORA_TEST_GRANTS_URL'])
        matrix = {
            'alembic_version': 'S', 'schools': 'SIUD', 'classrooms': 'SIUD',
            'subjects': 'SIUD', 'users': 'SIUD', 'feedbacks': 'SIUD',
            'trigger_keywords': 'SID', 'classroom_subjects': 'SID',
            'teacher_assignments': 'SID', 'teacher_subjects': 'SID',
            'auth_sessions': 'SIU', 'audit_events': 'I', 'admin_operations': 'SI',
            'reveal_permissions': 'S', 'reveal_requests': 'SIU',
            'maya_analyses': 'SI', 'maya_conversations': 'SI',
            'maya_questions': 'SIU', 'maya_daily_quotas': 'SIU',
        }
        script = (Path(__file__).resolve().parents[2] / 'deploy/postgres-grants.sql').read_text().replace('\\set ON_ERROR_STOP on', '')
        table = 'test_unknown_' + uuid4().hex
        with engine.connect().execution_options(isolation_level='AUTOCOMMIT') as conn:
            self.assertEqual(conn.scalar(text('SELECT current_database()')), 'echora')
            conn.exec_driver_sql(f'CREATE TABLE public.{table} (id serial PRIMARY KEY)')
            try:
                conn.exec_driver_sql(f'GRANT UPDATE (id) ON public.{table} TO echora_app')
                with conn.connection.driver_connection.cursor() as cursor:
                    cursor.execute(script)
                    cursor.execute(script)
                actual_tables = set(conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public'")).scalars())
                self.assertEqual(actual_tables, set(matrix) | {table})
                for name, allowed in matrix.items():
                    for letter, privilege in [('S','SELECT'), ('I','INSERT'), ('U','UPDATE'), ('D','DELETE'), ('T','TRUNCATE')]:
                        with self.subTest(table=name, privilege=privilege):
                            value = conn.scalar(text('SELECT has_table_privilege(:role, :table, :privilege)'),
                                                {'role': 'echora_app', 'table': 'public.' + name, 'privilege': privilege})
                            self.assertEqual(value, letter in allowed)
                    self.assertTrue(conn.scalar(text("SELECT has_table_privilege('echora_backup', :table, 'SELECT')"), {'table':'public.'+name}))
                    self.assertFalse(conn.scalar(text("SELECT has_table_privilege('echora_backup', :table, 'INSERT')"), {'table':'public.'+name}))
                for privilege in ('SELECT', 'INSERT', 'UPDATE', 'DELETE', 'TRUNCATE'):
                    self.assertFalse(conn.scalar(text("SELECT has_table_privilege('echora_app', :table, :privilege)"), {'table':'public.'+table, 'privilege':privilege}))
                self.assertFalse(conn.scalar(text("SELECT has_column_privilege('echora_app', :table, 'id', 'UPDATE')"), {'table':'public.'+table}))
                self.assertTrue(conn.scalar(text("SELECT has_table_privilege('echora_backup', :table, 'SELECT')"), {'table':'public.'+table}))
                self.assertTrue(conn.scalar(text("SELECT has_column_privilege('echora_app','public.audit_events','id','SELECT')")))
                self.assertTrue(conn.scalar(text("SELECT has_column_privilege('echora_app','public.audit_events','created_at','SELECT')")))
                self.assertFalse(conn.scalar(text("SELECT has_column_privilege('echora_app','public.audit_events','actor_id','SELECT')")))
                self.assertFalse(conn.scalar(text("SELECT has_sequence_privilege('echora_app', :sequence, 'USAGE')"), {'sequence':'public.'+table+'_id_seq'}))
                self.assertTrue(conn.scalar(text("SELECT has_sequence_privilege('echora_backup', :sequence, 'SELECT')"), {'sequence':'public.'+table+'_id_seq'}))
                owners = conn.execute(text("SELECT c.relname, r.rolname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace JOIN pg_roles r ON r.oid=c.relowner WHERE n.nspname='public' AND c.relkind IN ('r','S') AND c.relname NOT IN (:temp, :sequence)"), {'temp':table, 'sequence':table+'_id_seq'}).all()
                self.assertTrue(owners)
                self.assertTrue(all(owner == 'echora_migrator' for _, owner in owners), owners)
                self.assertEqual(conn.scalar(text("SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname=current_database()")), 'echora_migrator')
                self.assertEqual(conn.scalar(text("SELECT pg_get_userbyid(nspowner) FROM pg_namespace WHERE nspname='public'")), 'echora_migrator')
                for role in ('echora_app', 'echora_backup'):
                    self.assertFalse(conn.scalar(text("SELECT has_schema_privilege(:role, 'public', 'CREATE')"), {'role':role}))
            finally:
                conn.exec_driver_sql(f'DROP TABLE public.{table}')
        engine.dispose()
