import pytest
from django.db import connection


@pytest.mark.django_db
def test_database_connection_uses_postgresql_18():
    assert connection.vendor == "postgresql"
    assert connection.settings_dict["ENGINE"] == "django.db.backends.postgresql"

    with connection.cursor() as cursor:
        cursor.execute("SELECT current_setting('server_version_num'), 1")
        server_version, result = cursor.fetchone()

    assert 180000 <= int(server_version) < 190000
    assert result == 1
