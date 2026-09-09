#!/bin/bash
# Runs once, automatically, the first time the postgres container initializes
# an empty data volume (standard Postgres image behavior for anything mounted
# into /docker-entrypoint-initdb.d/). POSTGRES_DB is set to ${FERRETDB_DB}
# (see docker-compose.yml's postgres service comment) so DocumentDB's
# pg_cron-backed extension installs correctly - this script creates the
# app's own ${DB_NAME} database alongside it, in the same instance/volume,
# so `docker-compose up` stays a true one-command deploy with no manual
# `CREATE DATABASE` step required.
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE DATABASE "$DB_NAME";
    GRANT ALL PRIVILEGES ON DATABASE "$DB_NAME" TO "$POSTGRES_USER";
EOSQL
