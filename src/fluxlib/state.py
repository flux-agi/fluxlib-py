from dataclasses import dataclass
from abc import abstractmethod
from typing import Any, Dict, Optional, TypeVar, Generic

T = TypeVar('T')

@dataclass
class DataState:
    """
    Abstract base class defining the interface for state management.
    Implementations should provide concrete methods for state operations.
    """
    @abstractmethod
    def set(self, key: str, val: Any, opts: Optional[Dict[str, Any]] = None) -> None:
        """
        Set a value in the state.
        
        Args:
            key: The key to set
            val: The value to store
            opts: Optional settings for the operation
        """
        pass
    
    @abstractmethod
    def get(self, key: str) -> Any:
        """
        Get a value from the state.
        
        Args:
            key: The key to retrieve
            
        Returns:
            The stored value or None if not found
        """
        pass

    @abstractmethod
    def reset(self) -> None:
        """Reset the state to its initial empty condition."""
        pass

    @abstractmethod
    def delete(self, key: str) -> None:
        """
        Delete a key from the state.
        
        Args:
            key: The key to delete
        """
        pass 

class State:
    """
    Concrete implementation of state management with a simple dictionary backend.
    """
    def __init__(self, state: Optional[Dict[str, Any]] = None):
        """
        Initialize the state with an optional existing state dictionary.
        
        Args:
            state: Optional initial state dictionary
        """
        self._state: Dict[str, Any] = state or {}

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a value from the state.
        
        Args:
            key: The key to retrieve
            default: Value to return if key is not found
            
        Returns:
            The stored value or default if not found
        """
        try:
            return self._state[key]
        except KeyError:
            return default
    
    def set(self, key: str, val: Any, opts: Optional[Dict[str, Any]] = None) -> None:
        """
        Set a value in the state.
        
        Args:
            key: The key to set
            val: The value to store
            opts: Optional settings for the operation (unused in this implementation)
        """
        self._state[key] = val
    
    def delete(self, key: str) -> None:
        """
        Delete a key from the state.
        
        Args:
            key: The key to delete
            
        Note:
            Silently ignores keys that don't exist
        """
        try:
            del self._state[key]
        except KeyError:
            pass
    
    def reset(self) -> None:
        """Reset the state to an empty dictionary."""
        self._state = {}
    
    def get_all(self) -> Dict[str, Any]:
        """
        Get a copy of the entire state dictionary.
        
        Returns:
            A copy of the state dictionary
        """
        return self._state.copy()

class StateSlice:
    """
    Provides a namespaced view of a state object by prefixing all keys.
    """
    def __init__(self, state: Optional[Dict[str, Any]] = None, prefix: Optional[str] = None):
        """
        Initialize a state slice with an optional state and prefix.
        
        Args:
            state: The underlying state object or dictionary
            prefix: The prefix to apply to all keys
        """
        self._state = State(state)
        self.prefix = prefix or ""

    def _get_prefixed_key(self, key: str) -> str:
        """
        Create a prefixed key.
        
        Args:
            key: The original key
            
        Returns:
            The key with prefix applied
        """
        if not self.prefix:
            return key
        return f"{self.prefix}/{key}"

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a value from the state using a prefixed key.
        
        Args:
            key: The key to retrieve
            default: Value to return if key is not found
            
        Returns:
            The stored value or default if not found
        """
        return self._state.get(self._get_prefixed_key(key), default)
    
    def set(self, key: str, val: Any, opts: Optional[Dict[str, Any]] = None) -> None:
        """
        Set a value in the state using a prefixed key.
        
        Args:
            key: The key to set
            val: The value to store
            opts: Optional settings for the operation
        """
        self._state.set(self._get_prefixed_key(key), val, opts)
    
    def delete(self, key: str) -> None:
        """
        Delete a key from the state using a prefixed key.
        
        Args:
            key: The key to delete
        """
        self._state.delete(self._get_prefixed_key(key))

    def reset(self) -> None:
        """Reset the state to an empty dictionary."""
        self._state.reset()
        
    def get_all_with_prefix(self) -> Dict[str, Any]:
        """
        Get all state entries that match the current prefix.
        
        Returns:
            A dictionary with all matching entries
        """
        if not hasattr(self._state, 'get_all'):
            return {}
            
        all_state = self._state.get_all()
        prefix_len = len(self.prefix) + 1 if self.prefix else 0
        
        result = {}
        for key, value in all_state.items():
            if not self.prefix or key.startswith(f"{self.prefix}/"):
                # Strip the prefix from the key
                unprefixed_key = key[prefix_len:] if prefix_len > 0 else key
                result[unprefixed_key] = value
                
        return result