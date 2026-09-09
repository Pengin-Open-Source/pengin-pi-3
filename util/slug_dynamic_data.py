# util/slug_dynamic_data.py
# Storage for the actual field values a dynamic Slug's generated form
# collects - kept in FerretDB (via util.ferretdb.get_mongo_db()), not
# Postgres. Deliberately separate from Slug.json, which already has three
# other jobs (a datasource query descriptor, a static content dict, and -
# on a parent Slug - the JSON Schema definition itself); mixing a fourth,
# differently-shaped use into the same field would make all four modes
# harder to reason about. One Mongo collection, one document per dynamic
# child Slug, keyed by that Slug's own id (as a string) - no separate id
# scheme to keep in sync with Postgres.
#
# NOTE on cross-database consistency: a Slug row (Postgres) and its
# document here (FerretDB, via a completely separate connection/protocol)
# are never in the same transaction. save_dynamic_data() is always called
# right after the owning Slug is saved, and delete_dynamic_data() right
# before it's deleted, but a crash between the two steps can leave either
# side orphaned. Acceptable for now (staff-only feature, low write volume,
# and an orphaned FerretDB document costs nothing but a little disk); flag
# for reconciliation tooling if this feature sees real production use.
#
# NOTE on cascade deletes: if a parent (is_dynamic=True) Slug is deleted,
# Postgres CASCADEs the delete to its children at the SQL level - Django
# never calls delete_dynamic_data() for any of them, since Model.delete()
# is bypassed entirely by an FK CASCADE. Their FerretDB documents are
# orphaned. SlugDeleteView (main/views/slug.py) only cleans up the single
# Slug it's given - deleting a parent's whole dynamic-data tree needs its
# own cleanup pass, not yet built.
from util.ferretdb import get_mongo_db

COLLECTION_NAME = 'slug_dynamic_data'


def save_dynamic_data(slug_id, data):
    """Upserts the given slug's dynamic data document, replacing whatever
    was there before in full (not a partial merge - the caller always
    passes the complete current field set)."""
    db = get_mongo_db()
    db[COLLECTION_NAME].update_one(
        {'_id': str(slug_id)},
        {'$set': {'data': data}},
        upsert=True,
    )


def get_dynamic_data(slug_id):
    """Returns the stored field-value dict for this slug, or {} if none
    exists yet (a brand new dynamic slug with nothing submitted, or a
    non-dynamic slug that was never asked)."""
    db = get_mongo_db()
    doc = db[COLLECTION_NAME].find_one({'_id': str(slug_id)})
    return doc['data'] if doc else {}


def delete_dynamic_data(slug_id):
    db = get_mongo_db()
    db[COLLECTION_NAME].delete_one({'_id': str(slug_id)})
