from abc import ABC, abstractmethod
from typing import List, Dict, Any

class IRepository(ABC):
    @abstractmethod
    def load_data(self, path: str) -> List[Dict[str, Any]]:
        """Load telemetry or dataset from a source."""
        pass

    @abstractmethod
    def get_next_entry(self, index: int) -> Dict[str, Any]:
        """Get the entry at a specific index."""
        pass
