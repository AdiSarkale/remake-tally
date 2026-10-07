"""Provider abstraction for runtime application secrets.

The application stores secret references, not secret values. Concrete providers
can later be backed by AWS Secrets Manager, Azure Key Vault, HashiCorp Vault,
or another managed secret store without changing tenant-resolution code.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import json
import os

try:
    import boto3
except ImportError:  # pragma: no cover
    boto3 = None

from app.core.config import get_settings


class SecretProvider(ABC):
    """Resolve a secret value from an application-level reference."""

    @abstractmethod
    def get_secret(self, reference: str) -> str:
        """Return the secret value or raise RuntimeError if unavailable."""
        raise NotImplementedError


class AwsSecretsManagerProvider(SecretProvider):
    """Production provider backed by AWS Secrets Manager."""

    def __init__(self) -> None:
        if boto3 is None:
            raise RuntimeError("boto3 is required for AWS Secrets Manager")
        self.client = boto3.client("secretsmanager")

    def get_secret(self, reference: str) -> str:
        response = self.client.get_secret_value(SecretId=reference)
        value = response.get("SecretString")
        if value is None:
            binary = response.get("SecretBinary")
            if binary is None:
                raise RuntimeError(f"AWS secret has no value: {reference}")
            value = binary.decode() if isinstance(binary, bytes) else str(binary)
        return _extract_database_url(value, reference)


class EnvironmentSecretProvider(SecretProvider):
    """Development/demo provider backed by process environment variables."""

    prefix = "TENANT_DB_URL_"

    def get_secret(self, reference: str) -> str:
        value = os.getenv(f"{self.prefix}{reference}")
        if not value:
            raise RuntimeError(f"Tenant database secret is unavailable: {reference}")
        return value


def _extract_database_url(value: str, reference: str) -> str:
    """Accept a raw DB URL or JSON containing database_url."""
    value = value.strip()
    if value.startswith("{"):
        try:
            value = json.loads(value).get("database_url", "")
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"AWS secret is not valid JSON: {reference}") from exc
    if not value:
        raise RuntimeError(f"AWS secret does not contain database_url: {reference}")
    return value


def get_secret_provider() -> SecretProvider:
    """Return the configured provider.

    AWS Secrets Manager is used for production; environment-backed resolution remains available for local/demo use.
    """
    provider = get_settings().secret_provider.lower()
    if provider == "aws_secrets_manager":
        return AwsSecretsManagerProvider()
    if provider == "environment":
        return EnvironmentSecretProvider()
    raise RuntimeError(f"Unsupported secret provider: {provider}")
