from dataclasses import dataclass
from abc import abstractmethod

@dataclass
class DataState:
    @abstractmethod
    def set(self, key: str, val: any, opts: any):
        pass
    
    @abstractmethod
    def get(self, key: str):
        pass

    @abstractmethod
    def reset(self):
        pass

    @abstractmethod
    def delete(self, key: str):
        pass 

class State:
    def __init__(self):
        self._state = {}

    def get(self, key: str):
        return self._state[key]
    
    def set(self, key: str, val: any, opts: any):
        self._state[key] = val
        return
    
    def delete(self, key: str):
        del self._state[key]
        return
    
    def reset(self):
        self._state = {}
        return
    

class StateSlice():
    def __init__(self, state: DataState, prefix):
        self._state = state
        self.prefix = prefix

    def get(self, key: str):
        return self._state.get(f"{self.prefix}/{key}")
    
    def set(self, key: str, val: any, opts: any):
        self._state.set(f"{self.prefix}/{key}", val)
        return
    
    def delete(self, key: str):
        self._state.delete(f"{self.prefix}/{key}")
        return

    def reset(self):
        self._state = {}
        return