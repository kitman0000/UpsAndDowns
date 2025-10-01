from typing import Dict
from threading import Lock

class LockException(Exception):
    pass

class LockWithTimeout:
    def __init__(self, lock, timeout=1):
        self.lock = lock
        self.timeout = timeout

    def __enter__(self):
        if not self.lock.acquire(timeout=self.timeout):
            raise LockException("Unable to acquire the lock within the timeout")
        return self.lock

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.lock.release()

class LockManager:
    def __init__(self):
        self.lock_dict: Dict[str, Lock] = dict() # UUID, Lock
        self.manager_lock = Lock()
        
    def get_player_lock(self, uuid: str):
        with self.manager_lock:
            if uuid in self.lock_dict:
                return self.lock_dict[uuid]
            else:
                player_lock = Lock()
                self.lock_dict[uuid] = player_lock
                
                return player_lock