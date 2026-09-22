# Migration Verification Note

`alembic/versions/0001_initial_schema.py` was validated by generating its
full offline SQL output (`alembic upgrade head --sql`), since no live
PostgreSQL server was reachable in this environment (network egress is
allowlisted to package registries only, not arbitrary apt mirrors for
postgresql-server).

Result: **exit code 0**, clean generation of:
- all 27 `CREATE TYPE ... AS ENUM (...)` statements
- all 32 `CREATE TABLE` statements, in FK-dependency-safe order
- every composite `FOREIGN KEY(society_id, x) REFERENCES y (society_id, id)`
- every `CHECK` constraint
- every partial `CREATE UNIQUE INDEX ... WHERE ...`
- transaction wrapped in `BEGIN; ... COMMIT;`

See `docs/verified_initial_schema_output.sql` for the full generated SQL —
useful as a human-readable review artifact even though it's not run
directly (Alembic manages the actual migration).

**Not yet verified:** actual execution against a live PostgreSQL instance
(constraint semantics, trigger behavior, runtime errors). Run
`alembic upgrade head` against a real dev database before trusting this
in production — offline SQL generation catches structural/syntax issues
but not everything a live DB would.
