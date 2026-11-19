\set ON_ERROR_STOP on
-- Reaplicar como proprietário após cada migração. Tabelas não listadas não recebem escrita.
BEGIN;
DO $$
DECLARE r text;
BEGIN
  IF current_database() <> 'echora' THEN RAISE EXCEPTION 'Banco inesperado'; END IF;
  FOREACH r IN ARRAY ARRAY['echora_app','echora_backup'] LOOP
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname=r AND rolcanlogin AND NOT rolsuper
                   AND NOT rolcreatedb AND NOT rolcreaterole AND NOT rolreplication
                   AND NOT rolbypassrls AND NOT rolinherit)
       OR EXISTS (SELECT 1 FROM pg_auth_members m JOIN pg_roles x ON x.oid=m.member WHERE x.rolname=r)
    THEN RAISE EXCEPTION 'Role % ausente ou com privilégios inesperados', r; END IF;
  END LOOP;
  IF EXISTS (SELECT 1 FROM pg_database d JOIN pg_roles r ON r.oid=d.datdba WHERE d.datname=current_database() AND r.rolname IN ('echora_app','echora_backup'))
     OR EXISTS (SELECT 1 FROM pg_class c JOIN pg_roles r ON r.oid=c.relowner JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND r.rolname IN ('echora_app','echora_backup'))
  THEN RAISE EXCEPTION 'App ou backup é proprietário de objetos'; END IF;
END $$;

-- Retira grants anteriores, inclusive de tabelas futuras e de PUBLIC.
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM echora_app, echora_backup, PUBLIC;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM echora_app, echora_backup, PUBLIC;
-- REVOKE de tabela não remove grants por coluna existentes.
DO $$
DECLARE obj record;
BEGIN
  FOR obj IN
    SELECT c.oid::regclass AS relation, string_agg(quote_ident(a.attname), ', ') AS columns
    FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
    JOIN pg_attribute a ON a.attrelid=c.oid AND a.attnum > 0 AND NOT a.attisdropped
    WHERE n.nspname='public' AND c.relkind IN ('r','p','v','m','f')
    GROUP BY c.oid
  LOOP
    EXECUTE format('REVOKE SELECT (%s), INSERT (%s), UPDATE (%s), REFERENCES (%s) ON TABLE %s FROM echora_app, echora_backup, PUBLIC',
                   obj.columns, obj.columns, obj.columns, obj.columns, obj.relation);
  END LOOP;
END $$;

-- Backup precisa ler todo o esquema, inclusive objetos de migrações futuras.
GRANT SELECT ON ALL TABLES IN SCHEMA public TO echora_backup;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO echora_backup;

-- Inventário completo até a7d41e6b2c90: leitura apenas nas tabelas conhecidas.
GRANT SELECT ON TABLE public.alembic_version, public.schools, public.classrooms,
  public.subjects, public.trigger_keywords, public.classroom_subjects, public.users,
  public.feedbacks, public.teacher_assignments, public.teacher_subjects,
  public.auth_sessions, public.admin_operations,
  public.reveal_permissions, public.reveal_requests, public.maya_analyses,
  public.maya_conversations, public.maya_questions, public.maya_daily_quotas TO echora_app;
-- INSERT RETURNING do ORM precisa somente destas colunas de auditoria.
GRANT SELECT (id, created_at) ON TABLE public.audit_events TO echora_app;

-- Administração, criação e alteração de feedbacks, inclusive migração criptográfica.
GRANT INSERT, UPDATE, DELETE ON TABLE public.schools, public.classrooms,
  public.subjects, public.users, public.feedbacks TO echora_app;
GRANT INSERT, DELETE ON TABLE public.trigger_keywords, public.classroom_subjects,
  public.teacher_assignments, public.teacher_subjects TO echora_app;
-- Sessões rotativas são inseridas e revogadas/atualizadas; exclusão é por cascata.
GRANT INSERT, UPDATE ON TABLE public.auth_sessions TO echora_app;
-- Auditoria e idempotência são somente inserção; permissões de revelação, só leitura.
GRANT INSERT ON TABLE public.audit_events, public.admin_operations TO echora_app;
GRANT INSERT, UPDATE ON TABLE public.reveal_requests TO echora_app;
GRANT INSERT ON TABLE public.maya_analyses, public.maya_conversations TO echora_app;
GRANT INSERT, UPDATE ON TABLE public.maya_questions, public.maya_daily_quotas TO echora_app;

-- Somente sequências efetivamente usadas pelas inserções da aplicação.
GRANT USAGE, SELECT ON SEQUENCE public.schools_id_seq, public.classrooms_id_seq,
  public.subjects_id_seq, public.trigger_keywords_id_seq, public.feedbacks_id_seq,
  public.teacher_assignments_id_seq, public.audit_events_id_seq TO echora_app;
COMMIT;
