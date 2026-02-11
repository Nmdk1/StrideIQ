"""
P0-3 Security: Production startup hard-fail validation tests.

Verifies that invalid production config causes startup failure,
and that valid prod / non-prod configs work.
"""

from __future__ import annotations

import pytest

from core.config import validate_production_config


class TestProductionConfigValidation:
    """validate_production_config raises for bad prod config."""

    def test_production_debug_true_fails(self):
        with pytest.raises(ValueError, match="DEBUG must be False"):
            validate_production_config(
                environment="production",
                debug=True,
                cors_origins="https://strideiq.run",
                postgres_password="secure-password-12chars",
            )

    def test_production_cors_empty_fails(self):
        with pytest.raises(ValueError, match="CORS_ORIGINS"):
            validate_production_config(
                environment="production",
                debug=False,
                cors_origins="",
                postgres_password="secure-password-12chars",
            )

    def test_production_cors_none_fails(self):
        with pytest.raises(ValueError, match="CORS_ORIGINS"):
            validate_production_config(
                environment="production",
                debug=False,
                cors_origins=None,
                postgres_password="secure-password-12chars",
            )

    def test_production_cors_whitespace_only_fails(self):
        with pytest.raises(ValueError, match="CORS_ORIGINS"):
            validate_production_config(
                environment="production",
                debug=False,
                cors_origins="   ",
                postgres_password="secure-password-12chars",
            )

    def test_production_weak_password_postgres_fails(self):
        with pytest.raises(ValueError, match="POSTGRES_PASSWORD"):
            validate_production_config(
                environment="production",
                debug=False,
                cors_origins="https://strideiq.run",
                postgres_password="postgres",
            )

    def test_production_weak_password_short_fails(self):
        with pytest.raises(ValueError, match="POSTGRES_PASSWORD"):
            validate_production_config(
                environment="production",
                debug=False,
                cors_origins="https://strideiq.run",
                postgres_password="short",
            )

    def test_production_valid_config_passes(self):
        validate_production_config(
            environment="production",
            debug=False,
            cors_origins="https://strideiq.run,https://www.strideiq.run",
            postgres_password="secure-password-12chars",
        )


class TestNonProductionNotValidated:
    """Non-production configs are not validated."""

    def test_development_debug_true_passes(self):
        validate_production_config(
            environment="development",
            debug=True,
            cors_origins=None,
            postgres_password="postgres",
        )

    def test_development_default_password_passes(self):
        validate_production_config(
            environment="development",
            debug=False,
            cors_origins="",
            postgres_password="postgres",
        )

    def test_test_env_passes(self):
        validate_production_config(
            environment="test",
            debug=True,
            cors_origins=None,
            postgres_password="test",
        )
