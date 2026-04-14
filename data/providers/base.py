"""Base provider interface for all data sources."""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class BaseProvider(ABC):
    """Abstract base class for all data providers."""

    @abstractmethod
    def get_sports(self) -> List[Dict[str, Any]]:
        """Return list of available sports."""
        pass

    @abstractmethod
    def get_events(self, sport: str, **kwargs) -> List[Dict[str, Any]]:
        """Return list of upcoming events for a sport."""
        pass

    @abstractmethod
    def get_odds(self, sport: str, **kwargs) -> List[Dict[str, Any]]:
        """Return odds data for events in a sport."""
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the name of this provider."""
        pass
