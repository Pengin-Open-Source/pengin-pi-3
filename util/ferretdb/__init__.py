# Pengin-Pi-3 — Pengin Open Source
# util/ferretdb/__init__.py
#
# Connection helpers for FerretDB, the document store behind dynamic Slug data.
#
# Copyright (C) 2026 Tobu Pengin, L.L.C. and contributors
# Authors:
#   Stuart Anderson <stuart@tobupengin.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
import threading
from django.conf import settings
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, InvalidURI

# Live and in use: util.slug_dynamic_data (Slug's is_dynamic feature)
# stores its data here. FerretDB itself needs to be running a Postgres
# build with the DocumentDB extension - see docker-compose.yml's postgres
# service and .env.example's FERRETDB_DB - a plain postgres:15/16/17-alpine
# will not work (confirmed: every operation fails with "schema
# documentdb_api does not exist" against one).

def _connect(uri, **kwargs):
    """FerretDB logs in with the same DB_USER/DB_PASSWORD pair as Postgres
    (one set of secrets in .env - never separate Mongo credentials).
    docker-compose passes a credential-free MONGODB_URI
    (mongodb://ferretdb:27017/), so the pair is read from Django's own
    DATABASES setting and handed to pymongo as separate arguments - pymongo
    escapes them itself, so any password characters work. Building the
    password into the URI string instead breaks on RFC 3986 reserved
    characters (@ : / ? # %) with InvalidURI.

    An older deployment whose MONGODB_URI still embeds credentials keeps
    working: a URI that parses is used as-is, and one that doesn't (raw
    password with reserved characters) has its credentials split out."""
    hostpart = uri.partition('://')[2]
    if '@' not in hostpart:
        db = settings.DATABASES.get('default', {})
        if db.get('USER'):
            kwargs.setdefault('username', db['USER'])
            kwargs.setdefault('password', db.get('PASSWORD') or '')
        return MongoClient(uri, **kwargs)
    try:
        return MongoClient(uri, **kwargs)
    except InvalidURI:
        scheme, _, rest = uri.partition('://')
        userinfo, _, host = rest.rpartition('@')
        username, _, password = userinfo.partition(':')
        return MongoClient(f'{scheme}://{host}', username=username, password=password, **kwargs)


class MongoDBClient:
    _client = None
    _lock = threading.Lock()

    @classmethod
    def get_db(cls):
        if cls._client is None:
            with cls._lock:
                if cls._client is None:  # Double-check pattern for thread safety
                    cls._client = _connect(
                        settings.MONGODB_URI,
                        serverSelectionTimeoutMS=5000  # Fail fast if FerretDB is down
                    )
                    
                    # Proactively verify the FerretDB connection handshake
                    try:
                        cls._client.admin.command('ping')
                    except ConnectionFailure as e:
                        cls._client = None
                        raise ConnectionFailure(f"Could not connect to FerretDB: {e}")

        return cls._client[settings.MONGODB_DB_NAME]

# Helper function for easy importing
def get_mongo_db():
    return MongoDBClient.get_db()
