"""Provider abstraction for runtime application secrets.

The application stores secret references, not secret values. Concrete providers
can later be backed by AWS Secrets Manager, Azure Key Vault, HashiCorp Vault,
or another managed secret store without changing tenant-resolution code.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import os


class SecretProvider(ABC):
    """Resolve a secret value from an application-level reference."""

    @abstractmethod
    def get_secret(self, reference: str) -> str:
        """Return the secret value or raise RuntimeError if unavailable."""
        raise NotImplementedError


class EnvironmentSecretProvider(SecretProvider):
    """Development/demo provider backed by process environment variables."""

    prefix = "TENANT_DB_URL_"

    def get_secret(self, reference: str) -> str:
        value = os.getenv(f"{self.prefix}{reference}")
        if not value:
            raise RuntimeError(f"Tenant database secret is unavailable: {reference}")
        return value


def get_secret_provider() -> SecretProvider:
    """Return the configured provider.

    The first production-neutral implementation is environment-backed.
    A managed provider can replace this factory without changing callers.
    """
    return EnvironmentSecretProvider()
