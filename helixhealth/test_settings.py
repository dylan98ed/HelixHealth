import json
import os
import subprocess
import sys

SETTINGS_PROBE = """
import json
from helixhealth import settings

print(json.dumps({
    'debug': settings.DEBUG,
    'db_host': settings.DATABASES['default']['HOST'],
    'environment': settings.ENVIRONMENT,
    'secret_key': settings.SECRET_KEY,
}))
"""


def run_settings_probe(**environment):
    process_environment = os.environ.copy()
    for name in (
        "DJANGO_ENVIRONMENT",
        "DJANGO_DEBUG",
        "DJANGO_SECRET_KEY",
        "DB_HOST",
        "DB_PORT",
        "DB_NAME",
        "DB_USER",
        "DB_PASSWORD",
    ):
        process_environment.pop(name, None)
    process_environment.update(
        {
            "DB_HOST": "localhost",
            "DB_PORT": "5432",
            "DB_NAME": "helixhealth",
            "DB_USER": "helixhealth",
            "DB_PASSWORD": "settings-probe-only",
        }
    )
    process_environment.update(environment)

    return subprocess.run(
        [sys.executable, "-c", SETTINGS_PROBE],
        check=False,
        capture_output=True,
        env=process_environment,
        text=True,
    )


def test_production_requires_secret_key():
    result = run_settings_probe()

    assert result.returncode != 0
    assert "DJANGO_SECRET_KEY must be set" in result.stderr


def test_production_uses_environment_settings():
    result = run_settings_probe(
        DJANGO_ENVIRONMENT="production",
        DJANGO_DEBUG="false",
        DJANGO_SECRET_KEY="production-secret-from-environment",
    )

    assert result.returncode == 0, result.stderr
    settings = json.loads(result.stdout)
    assert settings == {
        "db_host": "localhost",
        "debug": False,
        "environment": "production",
        "secret_key": "production-secret-from-environment",
    }


def test_development_generates_ephemeral_secret():
    first_result = run_settings_probe(DJANGO_ENVIRONMENT="development")
    second_result = run_settings_probe(DJANGO_ENVIRONMENT="development")

    assert first_result.returncode == 0, first_result.stderr
    assert second_result.returncode == 0, second_result.stderr
    first_settings = json.loads(first_result.stdout)
    second_settings = json.loads(second_result.stdout)
    assert first_settings["debug"] is True
    assert first_settings["secret_key"] != second_settings["secret_key"]


def test_debug_rejects_ambiguous_values():
    result = run_settings_probe(
        DJANGO_ENVIRONMENT="development",
        DJANGO_DEBUG="sometimes",
    )

    assert result.returncode != 0
    assert "DJANGO_DEBUG must be a boolean value" in result.stderr


def test_database_environment_values_are_trimmed():
    result = run_settings_probe(
        DJANGO_ENVIRONMENT="production",
        DJANGO_SECRET_KEY="production-secret-from-environment",
        DB_HOST="  database.internal  ",
    )

    assert result.returncode == 0, result.stderr
    settings = json.loads(result.stdout)
    assert settings["db_host"] == "database.internal"


def test_whitespace_only_database_value_is_missing_in_production():
    result = run_settings_probe(
        DJANGO_ENVIRONMENT="production",
        DJANGO_SECRET_KEY="production-secret-from-environment",
        DB_HOST="  \t  ",
    )

    assert result.returncode != 0
    assert "DB_HOST must be set" in result.stderr


def test_local_environment_loader_accepts_utf8_bom(tmp_path, monkeypatch):
    from helixhealth.settings import load_local_environment

    environment_file = tmp_path / ".env"
    environment_file.write_text(
        "\ufeff# Windows-created environment file\nBOM_SAFE_VALUE=loaded\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("BOM_SAFE_VALUE", raising=False)

    load_local_environment(environment_file)

    assert os.environ["BOM_SAFE_VALUE"] == "loaded"
