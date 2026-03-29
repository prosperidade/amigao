import hashlib
import os
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.core.security import get_password_hash
from app.db.session import SessionLocal
from app.models.client import Client, ClientStatus, ClientType
from app.models.process import Process, ProcessPriority, ProcessStatus
from app.models.task import Task, TaskPriority, TaskStatus
from app.models.tenant import Tenant
from app.models.user import User


def _seed_password(env_name: str, fallback: str) -> str:
    value = os.getenv(env_name)
    if value:
        return value
    digest = hashlib.sha256(f"{settings.SECRET_KEY}:{env_name}".encode("utf-8")).hexdigest()
    return f"{fallback[:4]}!{digest[:10]}"


def _seed_reset_passwords() -> bool:
    return os.getenv("SEED_RESET_PASSWORDS", "false").strip().lower() in {"1", "true", "yes", "on"}


def _ensure_user(
    *,
    db,
    tenant_id: int,
    email: str,
    full_name: str,
    password: str,
    credentials_summary: list[str],
    reset_passwords: bool,
    is_superuser: bool = False,
) -> User:
    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(
            email=email,
            full_name=full_name,
            hashed_password=get_password_hash(password),
            tenant_id=tenant_id,
            is_active=True,
            is_superuser=is_superuser,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        print(f"User {email} created!")
        credentials_summary.append(f"{email} / {password} (created)")
        return user

    if reset_passwords:
        user.full_name = full_name
        user.hashed_password = get_password_hash(password)
        user.tenant_id = tenant_id
        user.is_active = True
        user.is_superuser = is_superuser
        db.add(user)
        db.commit()
        db.refresh(user)
        print(f"User {email} password rotated!")
        credentials_summary.append(f"{email} / {password} (rotated)")
        return user

    print(f"User {email} already exists.")
    credentials_summary.append(f"{email} / senha preservada (existing)")
    return user


def _ensure_client(
    *,
    db,
    tenant_id: int,
    full_name: str,
    email: str,
    client_type: ClientType,
    status: ClientStatus,
    phone: str,
    cpf_cnpj: str,
    source_channel: str,
    notes: str,
    legal_name: str | None = None,
) -> Client:
    client = (
        db.query(Client)
        .filter(Client.tenant_id == tenant_id, Client.email == email)
        .first()
    )
    if client:
        print(f"Client {email} already exists.")
        return client

    client = Client(
        tenant_id=tenant_id,
        full_name=full_name,
        legal_name=legal_name,
        email=email,
        phone=phone,
        cpf_cnpj=cpf_cnpj,
        client_type=client_type,
        status=status,
        source_channel=source_channel,
        notes=notes,
    )
    db.add(client)
    db.commit()
    db.refresh(client)
    print(f"Client {email} created!")
    return client


def _ensure_process(
    *,
    db,
    tenant_id: int,
    client_id: int,
    title: str,
    description: str,
    process_type: str,
    status: ProcessStatus,
    priority: ProcessPriority,
    responsible_user_id: int | None,
    opened_at: datetime | None = None,
    due_date: datetime | None = None,
    destination_agency: str | None = None,
    external_protocol_number: str | None = None,
    ai_summary: str | None = None,
    risk_score: float | None = None,
) -> Process:
    process = (
        db.query(Process)
        .filter(
            Process.tenant_id == tenant_id,
            Process.client_id == client_id,
            Process.title == title,
        )
        .first()
    )
    if process:
        print(f"Seeded process '{title}' already exists.")
        return process

    process = Process(
        tenant_id=tenant_id,
        client_id=client_id,
        title=title,
        description=description,
        process_type=process_type,
        status=status,
        priority=priority,
        urgency="normal",
        responsible_user_id=responsible_user_id,
        destination_agency=destination_agency,
        external_protocol_number=external_protocol_number,
        opened_at=opened_at,
        due_date=due_date,
        ai_summary=ai_summary,
        risk_score=risk_score,
    )
    db.add(process)
    db.commit()
    db.refresh(process)
    print(f"Seeded process '{title}' created!")
    return process


def _ensure_task(
    *,
    db,
    tenant_id: int,
    process_id: int,
    title: str,
    status: TaskStatus,
    priority: TaskPriority,
    created_by_user_id: int,
    assigned_to_user_id: int | None,
    description: str | None = None,
    due_date: datetime | None = None,
) -> Task:
    task = (
        db.query(Task)
        .filter(
            Task.tenant_id == tenant_id,
            Task.process_id == process_id,
            Task.title == title,
        )
        .first()
    )
    if task:
        print(f"Seeded task '{title}' already exists.")
        return task

    task = Task(
        tenant_id=tenant_id,
        process_id=process_id,
        title=title,
        description=description,
        status=status,
        priority=priority,
        created_by_user_id=created_by_user_id,
        assigned_to_user_id=assigned_to_user_id,
        due_date=due_date,
        completed_at=datetime.now(timezone.utc) if status == TaskStatus.concluida else None,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    print(f"Seeded task '{title}' created!")
    return task


def seed() -> None:
    if settings.is_production:
        raise RuntimeError("seed.py e um seed de demonstracao e nao deve ser executado em producao.")

    admin_password = _seed_password("SEED_ADMIN_PASSWORD", "admin123")
    consultant_password = _seed_password("SEED_CONSULTANT_PASSWORD", "consultor123")
    client_password = _seed_password("SEED_CLIENT_PASSWORD", "cliente123")
    field_password = _seed_password("SEED_FIELD_PASSWORD", "campo123")
    reset_passwords = _seed_reset_passwords()
    credentials_summary: list[str] = []
    now = datetime.now(timezone.utc)

    db = SessionLocal()
    try:
        tenant = db.query(Tenant).filter(Tenant.name == "Amigao Headquarters").first()
        if not tenant:
            tenant = Tenant(name="Amigao Headquarters")
            db.add(tenant)
            db.commit()
            db.refresh(tenant)

        admin_user = _ensure_user(
            db=db,
            tenant_id=tenant.id,
            email="admin@amigao.com",
            full_name="Administrador Global",
            password=admin_password,
            credentials_summary=credentials_summary,
            reset_passwords=reset_passwords,
            is_superuser=True,
        )
        consultant_user = _ensure_user(
            db=db,
            tenant_id=tenant.id,
            email="consultor@amigao.com",
            full_name="Consultor Demo",
            password=consultant_password,
            credentials_summary=credentials_summary,
            reset_passwords=reset_passwords,
        )
        client_user = _ensure_user(
            db=db,
            tenant_id=tenant.id,
            email="cliente@amigao.com",
            full_name="Cliente Demo",
            password=client_password,
            credentials_summary=credentials_summary,
            reset_passwords=reset_passwords,
        )
        field_user = _ensure_user(
            db=db,
            tenant_id=tenant.id,
            email="campo@amigao.com",
            full_name="Tecnico de Campo Demo",
            password=field_password,
            credentials_summary=credentials_summary,
            reset_passwords=reset_passwords,
        )

        portal_client = _ensure_client(
            db=db,
            tenant_id=tenant.id,
            full_name="Cliente Demo",
            email="cliente@amigao.com",
            client_type=ClientType.pf,
            status=ClientStatus.active,
            phone="(62) 99999-0000",
            cpf_cnpj="000.000.000-00",
            source_channel="seed",
            notes="Cliente ficticio para testes locais do portal do cliente.",
        )
        agribusiness_client = _ensure_client(
            db=db,
            tenant_id=tenant.id,
            full_name="Fazenda Boa Vista Agropecuaria",
            legal_name="Fazenda Boa Vista Agropecuaria Ltda",
            email="contato@boavista.amigao",
            client_type=ClientType.pj,
            status=ClientStatus.active,
            phone="(62) 3333-2000",
            cpf_cnpj="00.000.002/0001-00",
            source_channel="parceiro",
            notes="Conta seed para cenarios PJ e fluxo de execucao operacional.",
        )
        cooperative_client = _ensure_client(
            db=db,
            tenant_id=tenant.id,
            full_name="Cooperativa Agro do Cerrado",
            legal_name="Cooperativa Agro do Cerrado",
            email="cooperativa@cerrado.amigao",
            client_type=ClientType.pj,
            status=ClientStatus.lead,
            phone="(64) 3400-9900",
            cpf_cnpj="00.000.003/0001-00",
            source_channel="email",
            notes="Conta seed para validar status lead e funil comercial.",
        )

        process_specs = [
            {
                "client_id": portal_client.id,
                "title": "Prospeccao Ambiental - Sitio Agua Limpa",
                "description": "Processo seed em lead para validar entrada inicial do funil.",
                "process_type": "prospeccao",
                "status": ProcessStatus.lead,
                "priority": ProcessPriority.baixa,
                "responsible_user_id": consultant_user.id,
                "opened_at": now - timedelta(days=2),
                "due_date": now + timedelta(days=20),
            },
            {
                "client_id": portal_client.id,
                "title": "Retificacao CAR - Sitio Agua Limpa",
                "description": "Processo seed em triagem para testar intake e classificacao.",
                "process_type": "retificacao_car",
                "status": ProcessStatus.triagem,
                "priority": ProcessPriority.media,
                "responsible_user_id": consultant_user.id,
                "opened_at": now - timedelta(days=7),
                "due_date": now + timedelta(days=18),
            },
            {
                "client_id": portal_client.id,
                "title": "Desembargo IBAMA - Sitio Agua Limpa",
                "description": "Processo seed em diagnostico para validar etapa analitica.",
                "process_type": "desembargo",
                "status": ProcessStatus.diagnostico,
                "priority": ProcessPriority.alta,
                "responsible_user_id": consultant_user.id,
                "opened_at": now - timedelta(days=10),
                "due_date": now + timedelta(days=12),
            },
            {
                "client_id": agribusiness_client.id,
                "title": "Licenca Ambiental - Fazenda Boa Vista",
                "description": "Processo seed em planejamento para organizacao do escopo tecnico.",
                "process_type": "licenciamento",
                "status": ProcessStatus.planejamento,
                "priority": ProcessPriority.media,
                "responsible_user_id": consultant_user.id,
                "opened_at": now - timedelta(days=12),
                "due_date": now + timedelta(days=22),
            },
            {
                "client_id": agribusiness_client.id,
                "title": "Outorga de Agua - Fazenda Boa Vista",
                "description": "Processo seed em execucao com tarefas encadeadas para testes de campo.",
                "process_type": "outorga",
                "status": ProcessStatus.execucao,
                "priority": ProcessPriority.alta,
                "responsible_user_id": consultant_user.id,
                "opened_at": now - timedelta(days=14),
                "due_date": now + timedelta(days=10),
            },
            {
                "client_id": agribusiness_client.id,
                "title": "Regularizacao Fundiaria - Fazenda Boa Vista",
                "description": "Processo seed em protocolo para validar submissao documental.",
                "process_type": "regularizacao_fundiaria",
                "status": ProcessStatus.protocolo,
                "priority": ProcessPriority.critica,
                "responsible_user_id": consultant_user.id,
                "opened_at": now - timedelta(days=20),
                "due_date": now + timedelta(days=7),
                "destination_agency": "INCRA",
                "external_protocol_number": "PROC-LOCAL-2026-0042",
            },
            {
                "client_id": portal_client.id,
                "title": "Licenciamento Ambiental - Fazenda Boa Esperanca",
                "description": "Processo ficticio criado automaticamente para homologacao local.",
                "process_type": "licenciamento",
                "status": ProcessStatus.aguardando_orgao,
                "priority": ProcessPriority.media,
                "responsible_user_id": consultant_user.id,
                "opened_at": now - timedelta(days=14),
                "due_date": now + timedelta(days=15),
                "destination_agency": "SEMAD",
                "external_protocol_number": "PROC-LOCAL-2026-0001",
                "ai_summary": "Resumo simulado para validacao visual do portal do cliente.",
                "risk_score": 0.24,
            },
            {
                "client_id": portal_client.id,
                "title": "PRAD - Nascente Santa Rita",
                "description": "Processo seed em pendencia do orgao para testar retorno a execucao.",
                "process_type": "prad",
                "status": ProcessStatus.pendencia_orgao,
                "priority": ProcessPriority.alta,
                "responsible_user_id": consultant_user.id,
                "opened_at": now - timedelta(days=25),
                "due_date": now + timedelta(days=5),
                "destination_agency": "SEMAD",
                "external_protocol_number": "PROC-LOCAL-2026-0107",
            },
            {
                "client_id": agribusiness_client.id,
                "title": "Averbacao de Reserva Legal - Fazenda Boa Vista",
                "description": "Processo seed concluido para validar timeline e PDF.",
                "process_type": "averbacao_rl",
                "status": ProcessStatus.concluido,
                "priority": ProcessPriority.media,
                "responsible_user_id": consultant_user.id,
                "opened_at": now - timedelta(days=45),
                "due_date": now - timedelta(days=5),
                "destination_agency": "Cartorio de Registro",
                "external_protocol_number": "PROC-LOCAL-2026-0201",
                "ai_summary": "Processo encerrado com documentacao aprovada e registro finalizado.",
                "risk_score": 0.08,
            },
            {
                "client_id": cooperative_client.id,
                "title": "Licenca Previa - Unidade Rio Verde",
                "description": "Processo seed cancelado para validar encerramento antecipado.",
                "process_type": "licenca_previa",
                "status": ProcessStatus.cancelado,
                "priority": ProcessPriority.baixa,
                "responsible_user_id": admin_user.id,
                "opened_at": now - timedelta(days=6),
                "due_date": now + timedelta(days=30),
            },
            {
                "client_id": agribusiness_client.id,
                "title": "Arquivo Historico - Area Consolidada",
                "description": "Processo seed arquivado para validar visoes legadas.",
                "process_type": "historico",
                "status": ProcessStatus.arquivado,
                "priority": ProcessPriority.baixa,
                "responsible_user_id": admin_user.id,
                "opened_at": now - timedelta(days=90),
                "due_date": now - timedelta(days=60),
            },
        ]

        created_processes: dict[str, Process] = {}
        for spec in process_specs:
            created_processes[spec["title"]] = _ensure_process(
                db=db,
                tenant_id=tenant.id,
                client_id=spec["client_id"],
                title=spec["title"],
                description=spec["description"],
                process_type=spec["process_type"],
                status=spec["status"],
                priority=spec["priority"],
                responsible_user_id=spec["responsible_user_id"],
                opened_at=spec.get("opened_at"),
                due_date=spec.get("due_date"),
                destination_agency=spec.get("destination_agency"),
                external_protocol_number=spec.get("external_protocol_number"),
                ai_summary=spec.get("ai_summary"),
                risk_score=spec.get("risk_score"),
            )

        execution_process = created_processes["Outorga de Agua - Fazenda Boa Vista"]
        seeded_tasks = {
            "coleta_documentos": _ensure_task(
                db=db,
                tenant_id=tenant.id,
                process_id=execution_process.id,
                title="Coleta de documentos fundiarios",
                status=TaskStatus.concluida,
                priority=TaskPriority.medium,
                created_by_user_id=consultant_user.id,
                assigned_to_user_id=consultant_user.id,
                description="Checklist documental basico para abertura da outorga.",
                due_date=now - timedelta(days=8),
            ),
            "visita_tecnica": _ensure_task(
                db=db,
                tenant_id=tenant.id,
                process_id=execution_process.id,
                title="Visita tecnica ao imovel",
                status=TaskStatus.concluida,
                priority=TaskPriority.high,
                created_by_user_id=consultant_user.id,
                assigned_to_user_id=field_user.id,
                description="Captura de evidencias e validacao de campo.",
                due_date=now - timedelta(days=4),
            ),
            "levantamento_topografico": _ensure_task(
                db=db,
                tenant_id=tenant.id,
                process_id=execution_process.id,
                title="Levantamento topografico",
                status=TaskStatus.aguardando,
                priority=TaskPriority.high,
                created_by_user_id=consultant_user.id,
                assigned_to_user_id=field_user.id,
                description="Aguardando retorno do parceiro de georreferenciamento.",
                due_date=now + timedelta(days=3),
            ),
            "memorial_descritivo": _ensure_task(
                db=db,
                tenant_id=tenant.id,
                process_id=execution_process.id,
                title="Elaboracao do memorial descritivo",
                status=TaskStatus.em_progresso,
                priority=TaskPriority.high,
                created_by_user_id=consultant_user.id,
                assigned_to_user_id=consultant_user.id,
                description="Consolidacao tecnica para submissao ao orgao.",
                due_date=now + timedelta(days=5),
            ),
            "montagem_protocolo": _ensure_task(
                db=db,
                tenant_id=tenant.id,
                process_id=execution_process.id,
                title="Montagem do processo para protocolo",
                status=TaskStatus.backlog,
                priority=TaskPriority.medium,
                created_by_user_id=consultant_user.id,
                assigned_to_user_id=consultant_user.id,
                description="Ultima etapa antes de enviar a documentacao oficial.",
                due_date=now + timedelta(days=8),
            ),
        }

        dependency_pairs = [
            ("levantamento_topografico", "visita_tecnica"),
            ("memorial_descritivo", "levantamento_topografico"),
            ("montagem_protocolo", "memorial_descritivo"),
        ]
        dependencies_changed = False
        for task_key, dependency_key in dependency_pairs:
            task = seeded_tasks[task_key]
            dependency = seeded_tasks[dependency_key]
            if dependency not in task.dependencies:
                task.dependencies.append(dependency)
                dependencies_changed = True
        if dependencies_changed:
            db.commit()

        print("Seed credential summary:")
        for line in credentials_summary:
            print(f"  - {line}")
        if not reset_passwords:
            print("  - defina SEED_RESET_PASSWORDS=true para rotacionar as senhas derivadas do seed")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
