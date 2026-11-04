# Production database

Hoardrun runs on PostgreSQL (16 or newer). Local development uses a SQLite file and needs none of this.

## 0. First: rotate the old password

Until November 2026, `fintech_backend/app/config/settings.py` had a Supabase connection string, with its password, as the default `DATABASE_URL`. It's gone from the code, but it is still in the git history (commit `2c48dfc1`) and on GitHub.

1. In Supabase: **Project settings → Database → Reset database password.**
2. Update `DATABASE_URL` wherever the backend runs.
3. Check the database for anything you didn't create (unknown users, tables, rows).

Rewriting git history doesn't help once a secret has been pushed, so rotating the password is the fix.

## 1. Choose and set up the database

Any managed PostgreSQL 16+ works. Supabase is already in use. Whichever you choose, you need:

| Need | Why |
|---|---|
| **Point-in-time recovery** (Supabase Pro add-on; Neon, RDS and Cloud SQL include it) | Restore to the minute before a bad deploy or deletion. Daily backups alone can lose a day of money movements. |
| **A US region near the backend** (for example `us-east-1`) | US customers; and every request makes several queries, so distance from the backend adds up. The current Supabase project is in `eu-west-1`. |
| **Encryption at rest and TLS** | Included with every major provider; TLS is required by the app (`DATABASE_SSL_MODE=require`). |

Connect through a **session-mode pooler or a direct connection** (Supabase: port **5432**, not the 6543 transaction pooler). The app keeps its own small connection pool per process.

## 2. Two database users

| User | Used by | Can |
|---|---|---|
| The owner (`postgres` on Supabase) | Migrations only | Create and change tables |
| `hoardrun_app` | The running app (`DATABASE_URL`) | Read and write rows; nothing else |

Create `hoardrun_app` with [`fintech_backend/scripts/app_role.sql`](../fintech_backend/scripts/app_role.sql) after the first migration. It also sets a 30-second statement timeout so one slow query can't hold connections. This setup was tested on PostgreSQL 16: the whole app works as `hoardrun_app`, and it can't create tables.

## 3. Settings

| Variable | Value |
|---|---|
| `DATABASE_URL` | `postgresql://hoardrun_app:<password>@<host>:5432/<db>` (`postgres://` also works) |
| `DATABASE_SSL_MODE` | `require`, or `verify-full` once the provider's CA certificate is installed |
| `DATABASE_POOL_SIZE` / `DATABASE_MAX_OVERFLOW` | Defaults 5 / 5. Keep *processes × (size + overflow)* well under the plan's connection limit. |
| `DATA_ENCRYPTION_KEY` | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `ENVIRONMENT` | `production` |

`DATA_ENCRYPTION_KEY` encrypts bank tokens and account numbers stored in the database. **Store it in your password manager as well as the host.** A database backup is useless for those columns without it, and a new key can't read old rows.

In production the app refuses to start with no `DATABASE_URL` or a SQLite one.

## 4. Migrations

The schema is managed by Alembic (`fintech_backend/alembic/versions`). In production the app never creates tables. At startup it checks that the database is at the code's latest migration, and **refuses to start if it isn't** (or if it can't check).

From `fintech_backend`, with `MIGRATION_DATABASE_URL` (or `DATABASE_URL`) set to the **owner** connection. On the host, `MIGRATION_DATABASE_URL` is the owner and `DATABASE_URL` the app user, so the same settings serve both (see hosting.md):

```bash
python -m app.database.migrate status    # where the database is and what the code needs
python -m app.database.migrate upgrade   # apply migrations
```

**Every deploy:** run `upgrade` as the release step, before the new code starts (Render: *Pre-Deploy Command*; Heroku-style hosts: a `release:` line). If it fails, the old version keeps running.

**New database:** run `upgrade`, then `scripts/app_role.sql`.

**The existing Supabase database** was built by the old start-up code without migration history. Bring it under migrations once:

1. Take a backup (Supabase: *Database → Backups*, or `pg_dump`).
2. Run `python -m app.database.migrate adopt`.

`adopt` creates only the tables that are missing. It then records the database as up to date, but only if every existing table matches the code. If a column differs, it stops and lists the differences without changing anything. No rows are touched.

**Changing the schema later:** edit the model, then run

```bash
alembic revision --autogenerate -m "what changed"
```

Read the generated file (Alembic can't detect renames; it sees a drop and an add), then run `upgrade` on a copy before production. A new module with tables must also be added to `app/database/registry.py`, or migrations won't see it.

## 5. Check against real PostgreSQL

Unit tests run on SQLite. Before a release, run the app's main flows against an **empty** Postgres database:

```bash
DATABASE_URL=postgresql://.../scratch python -m app.database.migrate upgrade
DATABASE_URL=postgresql://.../scratch PYTHONPATH=. python scripts/postgres_smoke.py
```

It signs up two users and moves money through savings, budgets and sends, then checks notifications, export and health (24 checks). It refuses to run with `ENVIRONMENT=production`. Last result: 24/24 on PostgreSQL 16.2, also as `hoardrun_app`.

## 6. Backups and restores

- Keep point-in-time recovery on, with at least 7 days of history.
- **Every month, practise a restore:**
  1. Restore into a separate project or branch.
  2. Point `scripts/postgres_smoke.py` at it. The smoke script writes test users, so only ever run it against the restored copy, never production.
  3. Write down how long it took.
- Before risky migrations, take an on-demand backup.

## 7. Watch

- Connections in use against the plan limit.
- Slow queries (Supabase: *Query performance*; elsewhere `pg_stat_statements`).
- Disk use.
- Failed `upgrade` steps in deploy logs.
- `/api/health/database` (public). It shows the host and database name, never the password or raw errors.
