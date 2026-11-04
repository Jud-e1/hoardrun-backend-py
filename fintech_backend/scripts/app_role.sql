-- The database user the Hoardrun app connects as: it reads and writes data, but can't create,
-- change or drop tables. Migrations run as the owner (a separate, more powerful user).
--
-- Run once as the database owner, after `python -m app.database.migrate upgrade`, replacing
-- the password. Re-run the GRANT lines after a migration that adds tables (the default
-- privileges below cover tables the owner creates later, but re-running is harmless).

CREATE ROLE hoardrun_app LOGIN PASSWORD 'replace-with-a-long-random-password';

GRANT CONNECT ON DATABASE postgres TO hoardrun_app;  -- your database name
GRANT USAGE ON SCHEMA public TO hoardrun_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO hoardrun_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO hoardrun_app;
-- The app checks the migration version at startup but never changes it
REVOKE INSERT, UPDATE, DELETE ON alembic_version FROM hoardrun_app;

-- Tables and sequences the owner creates in future migrations
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO hoardrun_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO hoardrun_app;

-- Stop runaway queries holding connections
ALTER ROLE hoardrun_app SET statement_timeout = '30s';
ALTER ROLE hoardrun_app SET idle_in_transaction_session_timeout = '60s';
