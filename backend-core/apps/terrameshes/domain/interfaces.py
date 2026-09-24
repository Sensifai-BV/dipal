from abc import ABC, abstractmethod
from .entities import ProcessingTask

class TaskRepository(ABC):
    @abstractmethod
    def save(self, task: ProcessingTask):
        pass

    @abstractmethod
    def get_by_id(self, task_id: str) -> ProcessingTask:
        pass

    @abstractmethod
    def update(self, task: ProcessingTask):
        pass

class AIServiceClient(ABC):
    @abstractmethod
    def trigger_processing(self, task: ProcessingTask) -> bool:
        """Sends the request to the AI container/Lambda"""
        pass

class StorageService(ABC):
    @abstractmethod
    def check_file_exists(self, key: str) -> bool:
        pass
