from abc import ABC, abstractmethod
from typing import Optional
from .entities import JobEntity

class IJobRepository(ABC):
    @abstractmethod
    def create_job(self, job_entity: JobEntity) -> JobEntity:
       
        pass

    @abstractmethod
    def dataset_exists(self, dataset_id: int) -> bool:

        pass

class IQueueService(ABC):
    @abstractmethod
    def push_job_to_queue(self, job_id: int):

        pass
