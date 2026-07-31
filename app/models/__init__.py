from app.models.acao import (
    Acao,
    AcaoOrigem,
    AcaoPrioridade,
    AcaoStatus,
    AcaoTipoTriagem,
)
from app.models.ai_job import AIJob
from app.models.audit_log import AuditLog
from app.models.checklist_template import ChecklistTemplate, ProcessChecklist
from app.models.client import Client
from app.models.communication import CommunicationThread, Message
from app.models.contract import Contract
from app.models.contract_template import ContractTemplate
from app.models.credential import Credential, PortalType
from app.models.document import Document
from app.models.extracted_field_staging import ExtractedFieldStaging, ExtractedFieldStatus
from app.models.intake_classification_feedback import IntakeClassificationFeedback
from app.models.intake_draft import IntakeDraft, IntakeDraftState
from app.models.knowledge_catalog import KnowledgeChunk, SourceType
from app.models.legislation import LegislationDocument
from app.models.legislation_alert import LegislationAlert
from app.models.macroetapa import MacroetapaChecklist
from app.models.matricula import Matricula
from app.models.pre_cadastro import PreCadastro
from app.models.process import Process
from app.models.process_decision import ProcessDecision
from app.models.prompt_template import PromptTemplate
from app.models.property import Property
from app.models.proposal import Proposal
from app.models.regulatory import (
    DecisaoConsultor,
    ProcessIssueDecision,
    RegulatoryAlertFactibilidade,
    RegulatoryDiagnosis,
    RegulatoryFamilia,
    RegulatoryIssue,
    RegulatoryIssueCatalog,
    RegulatoryIssueSeverity,
    RegulatoryIssueType,
    StatusAchado,
    StatusSaneamento,
)
from app.models.rota import (
    Rota,
    RotaPasso,
    RotaPassoClassificacao,
    RotaPassoOrigem,
    RotaPassoStatus,
    RotaStatus,
    RotaVersao,
)
from app.models.stage_output import StageOutput
from app.models.task import Task
from app.models.tenant import Tenant
from app.models.user import User
from app.models.workflow_template import WorkflowTemplate
