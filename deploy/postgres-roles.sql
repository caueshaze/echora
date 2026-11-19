\set ON_ERROR_STOP on
-- Execute as the isolated cluster owner, before migrations. Set passwords with \password.
DO $$
DECLARE r text;
BEGIN
  IF current_database() <> 'echora' THEN RAISE EXCEPTION 'Banco inesperado'; END IF;
  FOREACH r IN ARRAY ARRAY['echora_migrator','echora_app','echora_backup'] LOOP
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname=r) THEN
      EXECUTE format('CREATE ROLE %I LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS', r);
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=r AND
      (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls OR rolinherit OR NOT rolcanlogin))
      OR EXISTS (SELECT 1 FROM pg_auth_members m JOIN pg_roles x ON x.oid=m.member WHERE x.rolname=r)
    THEN RAISE EXCEPTION 'Role % tem privilégios inesperados', r; END IF;
  END LOOP;
END $$;
ALTER DATABASE echora OWNER TO echora_migrator;
ALTER SCHEMA public OWNER TO echora_migrator;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT CONNECT ON DATABASE echora TO echora_app, echora_backup;
GRANT USAGE ON SCHEMA public TO echora_app, echora_backup;
