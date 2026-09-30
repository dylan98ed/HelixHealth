"""Shared limits for files produced and accepted by the exchange profile."""

MAX_BUNDLE_BYTES = 2 * 1024 * 1024
MAX_BUNDLE_ENTRIES = 500
# Three shared context resources and three vital-sign observations per admission.
MAX_EXPORTED_ADMISSIONS = (MAX_BUNDLE_ENTRIES - 3) // 3
