import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

PATIENT_TABLE = "patients_patient"
INITIAL_MIGRATION = ("patients", "0001_initial")


@pytest.mark.django_db(transaction=True)
def test_initial_patient_migration_applies_and_rolls_back():
    executor = MigrationExecutor(connection)
    latest_migrations = executor.loader.graph.leaf_nodes()

    try:
        executor.migrate([("patients", None)])
        assert PATIENT_TABLE not in connection.introspection.table_names()

        executor = MigrationExecutor(connection)
        executor.migrate([INITIAL_MIGRATION])
        assert PATIENT_TABLE in connection.introspection.table_names()

        executor = MigrationExecutor(connection)
        executor.migrate([("patients", None)])
        assert PATIENT_TABLE not in connection.introspection.table_names()
    finally:
        MigrationExecutor(connection).migrate(latest_migrations)
