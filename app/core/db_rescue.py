"""Escrita de socorro numa sessão que pode estar envenenada.

A Frente K (12/09) mediu a primeira ocorrência desta classe em
``consolidate_process_endpoint``: um ``DataError`` no ``flush`` abortou a
transação, o bloco de resgate leu ``current_user.tenant_id`` (lazy-load) e
morreu de ``PendingRollbackError`` ANTES de registrar a auditoria. O socorro
morria antes de socorrer.

A Frente L varreu o projeto pela classe e achou mais quatro pontos com o mesmo
desenho: um ``except`` que tenta gravar o desfecho da falha na MESMA sessão que
a falha acabou de derrubar. O resultado é sempre o mesmo — o registro do
fracasso não acontece, e o erro que chega ao topo é o ``PendingRollbackError``
genérico no lugar da causa real.

Regra desta porta, em uma frase: **rede de segurança não pode depender do que
acabou de cair**. Quem quer gravar depois de um erro de banco desfaz a
transação morta primeiro, recarrega a linha pelo identificador (nunca pelo
objeto ORM já expirado) e só então escreve.
"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.logging import get_logger

logger = get_logger(__name__)


def gravar_desfecho_de_falha(
    db: Session,
    model: type[Any],
    pk: Optional[int],
    **campos: Any,
) -> bool:
    """Grava ``campos`` na linha ``pk`` depois de desfazer a transação morta.

    Devolve ``True`` se gravou. Uso típico::

        except Exception as exc:
            gravar_desfecho_de_falha(
                db, Document, doc_id,
                ocr_status=OcrStatus.failed,
                ocr_error="...",
            )

    Requer que a sessão seja do chamador (worker com ``SessionLocal()`` próprio).
    Serviço que roda dentro da transação de outro (request) não pode desfazer o
    que o chamador ainda não gravou — ali o desenho certo é ``begin_nested()``
    em volta do trecho arriscado (ver ``legislation_service.ingest_*``).

    O ``rollback`` é incondicional de propósito: o trabalho do ``try`` falhou e
    não deve ser gravado de qualquer modo, e perguntar antes ("a sessão está
    ativa?") acopla o socorro ao estado interno do SQLAlchemy — exatamente o que
    quebrou antes.
    """
    if pk is None:
        logger.error(
            "socorro sem identificador: %s não pôde registrar o desfecho da falha",
            model.__name__,
        )
        return False

    try:
        db.rollback()
        obj = db.get(model, pk)
        if obj is None:
            logger.error(
                "socorro: %s id=%s não existe mais — desfecho da falha não registrado",
                model.__name__, pk,
            )
            return False
        for nome, valor in campos.items():
            setattr(obj, nome, valor)
        db.add(obj)
        db.commit()
        return True
    except Exception:
        # Falhou o próprio socorro. Não há terceira rede: o que resta é gritar.
        # Engolir aqui (o `except Exception: pass` que havia nos workers) é o que
        # fazia um AIJob ficar "running" para sempre, sem nenhuma linha de log.
        logger.exception(
            "socorro FALHOU: %s id=%s ficou sem registro de desfecho",
            model.__name__, pk,
        )
        return False
