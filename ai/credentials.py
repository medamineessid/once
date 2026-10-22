"""Credential sources for optional cloud providers."""

from __future__ import annotations

import os
from typing import Protocol

from engine.errors import AIProviderError


class CredentialSource(Protocol):
    """Read one secret without exposing it to logs or ordinary config files."""

    def get(self, name: str) -> str | None:
        """Return a secret or None when it is unavailable."""


class EnvironmentCredentialSource:
    """Development/testing fallback backed by process environment variables."""

    def get(self, name: str) -> str | None:
        return os.environ.get(name)


class WindowsCredentialManagerSource:
    """Read a generic credential from Windows Credential Manager."""

    def get(self, name: str) -> str | None:
        if os.name != "nt":
            raise AIProviderError("Windows Credential Manager is available only on Windows.")
        try:
            import win32cred

            credential = win32cred.CredRead(name, win32cred.CRED_TYPE_GENERIC)
        except (ImportError, OSError) as error:
            raise AIProviderError("Could not read Windows Credential Manager.") from error
        blob = credential.get("CredentialBlob", b"")
        return blob.decode("utf-8").rstrip("\x00")


def configured_gemini_key() -> str | None:
    """Read Gemini credentials from Windows storage, then the development fallback."""
    if os.name == "nt":
        try:
            key = WindowsCredentialManagerSource().get("Once/Gemini")
        except AIProviderError:
            key = None
        if key:
            return key
    return EnvironmentCredentialSource().get("ONCE_GEMINI_API_KEY")
