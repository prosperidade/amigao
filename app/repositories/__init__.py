from app.repositories.client_repo import ClientRepository
from app.repositories.document_repo import DocumentRepository
from app.repositories.matricula_repo import MatriculaRepository
from app.repositories.process_repo import ProcessRepository
from app.repositories.property_repo import PropertyRepository
from app.repositories.staging_repo import ExtractedFieldStagingRepository
from app.repositories.task_repo import TaskRepository

__all__ = [
    "ClientRepository",
    "DocumentRepository",
    "ExtractedFieldStagingRepository",
    "MatriculaRepository",
    "ProcessRepository",
    "PropertyRepository",
    "TaskRepository",
]
