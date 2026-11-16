"""Compatibility import for backend callers of the shared configuration."""

from src.shared.config import Settings, settings

__all__ = ["Settings", "settings"]
