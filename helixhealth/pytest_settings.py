import os
from importlib import import_module

os.environ["DJANGO_ENVIRONMENT"] = "test"
os.environ.setdefault("DJANGO_SECRET_KEY", "pytest-only-secret-key")

_base_settings = import_module("helixhealth.settings")
globals().update(
    {
        name: getattr(_base_settings, name)
        for name in dir(_base_settings)
        if name.isupper()
    }
)
