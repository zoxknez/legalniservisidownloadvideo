"""Abstract base for all service engines."""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class AbstractServiceEngine(ABC):
    """Defines the contract every download-service engine must fulfill."""

    @staticmethod
    @abstractmethod
    def is_supported() -> bool:
        """Return True if this engine's runtime dependencies are available."""

    @staticmethod
    @abstractmethod
    def health_check() -> Dict[str, Any]:
        """Return a status dict used by /api/status."""

    @abstractmethod
    def download(
        self,
        url: str,
        output_dir: str,
        *,
        quality: Optional[str] = None,
        extra_args: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Start a download and return at least {"title": str, "cmd": list}."""

    def login(self, **credentials: str) -> Dict[str, Any]:
        """Authenticate with the upstream service (optional)."""
        raise NotImplementedError(f"{type(self).__name__} does not require login")
