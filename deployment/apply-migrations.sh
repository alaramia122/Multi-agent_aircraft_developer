#!/bin/sh
set -eu

: "${PGHOST:?PGHOST is required}"
: "${PGDATABASE:?PGDATABASE is required}"
: "${PGUSER:?PGUSER is required}"
: "${PGPASSWORD:?PGPASSWORD is required}"

psql --set ON_ERROR_STOP=1 <<'SQL'
CREATE TABLE IF NOT EXISTS gateway_schema_migrations (
    migration_name TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
SQL

apply_migration() {
    migration_path="$1"
    migration_name="$(basename "$migration_path")"

    applied="$(
        psql \
            --tuples-only \
            --no-align \
            --set ON_ERROR_STOP=1 \
            --set migration_name="$migration_name" \
            --command "SELECT 1 FROM gateway_schema_migrations WHERE migration_name = :'migration_name';"
    )"

    if [ "$applied" = "1" ]; then
        echo "Skipping already applied migration: $migration_name"
        return
    fi

    echo "Applying migration: $migration_name"
    migration_batch="$(mktemp)"
    {
        printf '\\set ON_ERROR_STOP on\n'
        printf 'BEGIN;\n'
        cat "$migration_path"
        printf '\nINSERT INTO gateway_schema_migrations (migration_name) VALUES ('
        printf "'%s'" "$migration_name"
        printf ');\nCOMMIT;\n'
    } > "$migration_batch"

    psql --file "$migration_batch"
    rm -f "$migration_batch"
}

for migration_path in /migrations/versions/*.sql; do
    apply_migration "$migration_path"
done

for migration_path in /migrations/*.sql; do
    apply_migration "$migration_path"
done
