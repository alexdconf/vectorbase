"""
Database router for VectorBase.

The `vectors` database is the pre-populated pgvector database.
It is accessed exclusively via raw SQL (django.db.connections['vectors'])
and must never receive Django migrations.

All ORM models (portal.DailyQuota, logs.SearchLog, Django internals)
live on the `default` database.
"""


class VectorsDatabaseRouter:
    def db_for_read(self, model, **hints):
        return "default"

    def db_for_write(self, model, **hints):
        return "default"

    def allow_relation(self, obj1, obj2, **hints):
        return True

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        # Migrations only ever touch the default DB.
        return db == "default"
