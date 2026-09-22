"""Entrada única: fonte versionada → observação durável → projeção de staging."""
import json
import re
from collections import Counter
from datetime import date

from fastapi import HTTPException
from pydantic import TypeAdapter, ValidationError

from app.models.document import Document, DocumentSource
from app.models.entrada_semantica import ClassificacaoDocumento, DocumentoVersao
from app.models.evidence import EvidenceInvalidation
from app.models.extracted_field_staging import ExtractedFieldStaging, ExtractedFieldStatus
from app.schemas.entrada_semantica import (
    AtoExtraido,
    ContratoExtraido,
    EntradaExtraida,
    EspecieDocumental,
    FalecimentoDeclarado,
    ObservacaoExtraida,
    ParteExtraida,
    ParticipacaoExtraida,
    ReferenciaProcesso,
)
from app.schemas.evidence import EvidenceAttributes, EvidenceRef
from app.services.documento_versao import registrar_fragmento, registrar_leitura
from app.services.evidence import (
    _capture,
    authorize,
    invalidate_dependents,
    latest_objects,
    lock_case,
    reviews_by_evidence,
)
from app.services.identidade_observacao import (
    identidade_observacao,
    localizar_trecho,
    normalizar_conteudo,
    resolver_ancora_literal,
)
from app.services.taxonomia_documental import SUPORTE, destino_consolidavel, propor_especie


def classificacao_atual(db, doc):
    return db.query(ClassificacaoDocumento).filter_by(tenant_id=doc.tenant_id,
        documento_id=doc.id).order_by(ClassificacaoDocumento.versao.desc()).first()


def fonte_documental(db, doc):
    versao = db.query(DocumentoVersao).filter_by(tenant_id=doc.tenant_id,
        documento_id=doc.id).order_by(DocumentoVersao.numero.desc()).first()
    classificacao = classificacao_atual(db, doc)
    especie = (classificacao.tipo_revisado or classificacao.tipo_proposto) if classificacao else "indeterminada"
    return _capture(db, doc.tenant_id, doc.process_id, f"document:{doc.id}", "fonte_primaria", {
        "origin": "documento", "attributes": {
            "document_id": doc.id, "document_version": versao.numero if versao else doc.version_number,
            "documento_versao_id": versao.id if versao else None,
            "original_hash": versao.sha256_original if versao else doc.checksum_sha256,
            "literal": versao.texto if versao else doc.extracted_text,
            "text_hash": versao.sha256_texto if versao else None,
            "method": versao.metodo if versao else "legado_nao_versionado",
        }, "limits": [SUPORTE[especie]], "legacy_unverified": versao is None,
    }, source_record={"text": versao.texto if versao else doc.extracted_text,
        "storage_key": doc.storage_key, "document_type": especie, "name": doc.original_file_name,
        "classificacao_versao": classificacao.versao if classificacao else None})


def reclassificar(db, tenant_id, user_id, process_id, document_id, especie, motivo, expected_version):
    authorize(db, tenant_id, user_id, process_id)
    lock_case(db, tenant_id, process_id)
    doc = db.query(Document).filter_by(id=document_id, tenant_id=tenant_id, process_id=process_id).first()
    if doc is None:
        raise HTTPException(404, "Documento não encontrado no caso")
    old = classificacao_atual(db, doc)
    if expected_version != (old.versao if old else 0):
        raise HTTPException(409, "Classificação mudou; recarregue")
    row = ClassificacaoDocumento(tenant_id=tenant_id, documento_id=doc.id,
        versao=expected_version + 1, tipo_original=old.tipo_original if old else doc.document_type,
        tipo_proposto=old.tipo_proposto if old else propor_especie(doc.extracted_text, doc.document_type),
        tipo_revisado=EspecieDocumental(especie).value, responsavel_id=user_id, motivo=motivo)
    db.add(row)
    doc.review_required = True
    doc.extraction_status = "tipo reclassificado — extrações dependentes desatualizadas; revisar e reextrair"
    db.flush()
    fonte_documental(db, doc)  # New source version invalidates the entire dependent graph.
    return {"versao": row.versao, "tipo_revisado": row.tipo_revisado, "revisao_necessaria": True}


def conteudo_do_item(item):
    """Proposed content plus the fields emptied for lack of support in the item's anchor."""
    content = item.model_dump(mode="json")
    if item._campos_sem_suporte:
        content["campos_sem_suporte"] = item._campos_sem_suporte
    return content


def campos_sem_suporte(entrada):
    """Emptied fields of the surviving items, for the extraction report."""
    items = [*entrada.partes, *entrada.todas_participacoes, *entrada.atos, *entrada.observacoes,
             *entrada.contratos, *entrada.falecimentos_declarados, *entrada.referencias_processo]
    return [campo for item in items for campo in item._campos_sem_suporte]


def persistir_entrada(db, doc, entrada: EntradaExtraida, *, metodo="extrator_semantico", modelo=None):
    with db.begin_nested():
        return _persistir_entrada(db, doc, entrada, metodo=metodo, modelo=modelo)


def _persistir_entrada(db, doc, entrada: EntradaExtraida, *, metodo="extrator_semantico", modelo=None):
    if doc.process_id is None:
        raise HTTPException(422, "Entrada semântica exige caso autorizado")
    lock_case(db, doc.tenant_id, doc.process_id)
    version = db.query(DocumentoVersao).filter_by(tenant_id=doc.tenant_id,
        documento_id=doc.id).order_by(DocumentoVersao.numero.desc()).first()
    if version is None:
        version = registrar_leitura(db, doc, doc.extracted_text or "", metodo="legado",
            origem="legado", parametros={"legacy_unverified": True})
    classification = classificacao_atual(db, doc)
    if classification is None:
        classification = ClassificacaoDocumento(tenant_id=doc.tenant_id, documento_id=doc.id,
            versao=1, tipo_original=doc.document_type, tipo_proposto=propor_especie(version.texto, doc.document_type),
            motivo="proposta por identidade documental; aguarda revisão")
        db.add(classification)
        db.flush()
    especie = classification.tipo_revisado or classification.tipo_proposto
    if especie == "comprovante_situacao_cadastral_cpf" and (
            any(p.natureza == "espolio" for p in entrada.partes) or entrada.contratos or entrada.todas_participacoes):
        raise HTTPException(422, "Receita não fundamenta espólio, contrato ou representação")
    source = fonte_documental(db, doc)
    refs = []
    # Preserve every extracted item, including acts and participants with no cadastral target.
    items = [("parte", conteudo_do_item(x), x.trecho) for x in entrada.partes]
    items += [("observacao", conteudo_do_item(x), x.trecho) for x in entrada.observacoes]
    items += [("ato_registral", conteudo_do_item(x), x.trecho) for x in entrada.atos]
    items += [("participacao", conteudo_do_item(x), x.trecho) for x in entrada.todas_participacoes]
    items += [("contrato", {**conteudo_do_item(x), "predicado": especie}, x.trecho) for x in entrada.contratos]
    items += [("falecimento_declarado", conteudo_do_item(x), x.trecho) for x in entrada.falecimentos_declarados]
    items += [("referencia_processo", conteudo_do_item(x), x.trecho) for x in entrada.referencias_processo]
    for tipo, item, trecho in items:
        try:
            start = localizar_trecho(version.texto, trecho, item.get("posicao_inicio"))
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        fragment = registrar_fragmento(db, version, start, start + len(trecho))
        if tipo == "falecimento_declarado":
            if especie != "comprovante_situacao_cadastral_cpf" or "titular falecido" not in trecho.lower():
                raise HTTPException(422, "Falecimento declarado exige comprovante Receita e trecho TITULAR FALECIDO")
            if item["ano"] is not None and not re.search(rf"\b{item['ano']}\b", trecho):
                raise HTTPException(422, "Ano de falecimento ausente do trecho")
            if item["data_consulta"]:
                consulta = date.fromisoformat(item["data_consulta"])
                if not any(value in trecho for value in (consulta.isoformat(), consulta.strftime("%d/%m/%Y"))):
                    raise HTTPException(422, "Data da consulta ausente do trecho")
        if tipo == "contrato":
            if especie not in {"contrato_particular", "contrato_servico_documental"}:
                raise HTTPException(422, "Contratação exige espécie contratual revisável")
            for representacao in item["representacao_declarada"]:
                representacao["estado_confirmacao"] = "declarado"
            item["lacunas"] = [campo for campo in ("contratante", "contratado", "objeto") if not item[campo]]
        if tipo == "referencia_processo" and (especie not in ESPECIES_CONTRATUAIS
                or re.sub(r"\s+", "", item["numero"]) not in re.sub(r"\s+", "", trecho)):
            raise HTTPException(422, "Referência a processo exige família contratual e o número no trecho")
        if tipo == "participacao":
            # The model cannot promote its own declaration to confirmation.
            item["estado_confirmacao"] = "declarado"
        predicate = item.get("predicado", tipo)
        object_id = identidade_observacao(doc.id, version.numero, classification.versao, tipo, item,
            start, start + len(trecho))
        attrs = EvidenceAttributes(document_id=doc.id, document_version=version.numero,
                documento_versao_id=version.id, fragmento_id=fragment.id, original_hash=version.sha256_original,
                text_hash=version.sha256_texto, predicate=predicate, literal=trecho,
                normalized=normalizar_conteudo(item), unit=item.get("unidade"), subject=item.get("sujeito"),
                role=item.get("papel"), anchor=trecho, position=f"[{start},{start + len(trecho)})",
                method=metodo, method_version="071.2")
        row = _capture(db, doc.tenant_id, doc.process_id, object_id, "observacao", {
            "origin": "extrator", "attributes": attrs.model_dump(mode="json"),
            "premises": [EvidenceRef(id=source.object_id, version=source.version).model_dump()],
            "limits": [SUPORTE[especie]],
        }, source_record={"tipo_entrada": tipo, "especie_documental": especie})
        if all(existing.id != row.id for existing in refs):
            refs.append(row)
        target = destino_consolidavel(especie, predicate) if tipo == "observacao" else None
        # These rows are review projections, not new assertions and not Client fields.
        sem_destino = tipo in {"parte", "participacao", "contrato", "ato_registral", "falecimento_declarado",
                               "referencia_processo"}
        if (target or sem_destino) and not db.query(ExtractedFieldStaging.id).filter_by(observacao_ref=row.id).first():
            db.add(ExtractedFieldStaging(tenant_id=doc.tenant_id, process_id=doc.process_id,
                document_id=doc.id, observacao_ref=row.id, source_doc_type=especie,
                field_name=predicate, field_value={"value": normalizar_conteudo(item) if sem_destino else item.get("valor"),
                    "unidade": item.get("unidade"), "ancora": {
                        "trecho": trecho, "pos": start, "start": start, "end": start + len(trecho)}},
                tipo_observacao=tipo if sem_destino else None, atributos=normalizar_conteudo(item) if sem_destino else None,
                target_entity=target[0] if target else None, target_field=target[1] if target else None,
                status=ExtractedFieldStatus.pendente, created_by_agent="extrator"))
    db.flush()
    persistir_entidades(db, doc, entrada, refs, especie)
    return refs


def persistir_entidades(db, doc, entrada, refs, especie):
    from app.models.entrada_semantica import (
        AtoRegistral,
        Espolio,
        Participacao,
        Pessoa,
        PessoaIdentificador,
        RelacaoAto,
        Serventia,
    )
    def fundamento_do(tipo, item):
        normalized = normalizar_conteudo(conteudo_do_item(item))
        if tipo == "participacao":
            normalized["estado_confirmacao"] = "declarado"
        start = localizar_trecho(doc.extracted_text, item.trecho, item.posicao_inicio)
        position = f"[{start},{start + len(item.trecho)})"
        matches = [r for r in refs if (r.source_record or {}).get("tipo_entrada") == tipo
                   and r.content["attributes"]["normalized"] == normalized
                   and r.content["attributes"].get("position") == position]
        if len(matches) != 1:
            raise HTTPException(422, "Fundamento da entidade ausente ou ambíguo")
        return matches[0]
    pessoas, espolios, atos = {}, {}, {}
    fundamentos = {r.content["attributes"]["normalized"].get("chave"): r
                   for r in refs if (r.source_record or {}).get("tipo_entrada") == "parte"}
    for parte in entrada.partes:
        if parte.natureza == "espolio":
            continue
        # Unused names without a sourced participation are not identities to merge.
        fundamento = fundamentos.get(parte.chave)
        if fundamento is None:
            raise HTTPException(422, "Parte sem observação ancorada")
        row = db.query(Pessoa).filter_by(tenant_id=doc.tenant_id, origem_observacao_id=fundamento.id).first()
        if row is None:
            row = Pessoa(tenant_id=doc.tenant_id, nome=parte.nome, natureza=parte.natureza,
                aliases=[], origem_observacao_id=fundamento.id)
            db.add(row)
            db.flush()
        pessoas[parte.chave] = row
        fundamento = fundamentos.get(parte.chave)
        if parte.identificador and parte.tipo_identificador and fundamento:
            # Literal identifier must itself be visible in the source; no borrowed representative CPF.
            if re.sub(r"\s+", "", parte.identificador) not in re.sub(r"\s+", "", parte.trecho):
                raise HTTPException(422, "Identificador não localizado no documento")
            if not db.query(PessoaIdentificador.id).filter_by(tenant_id=doc.tenant_id,
                    pessoa_id=row.id, fundamento_id=fundamento.id).first():
                db.add(PessoaIdentificador(tenant_id=doc.tenant_id, pessoa_id=row.id,
                    tipo=parte.tipo_identificador, valor=parte.identificador,
                    fundamento_id=fundamento.id, estado_confirmacao="declarado"))
    for declaracao in entrada.falecimentos_declarados:
        pessoa = pessoas[declaracao.sujeito]
        fundamento = fundamento_do("falecimento_declarado", declaracao)
        pessoa.estado = "falecimento_declarado"
        pessoa.estado_fundamento_id = fundamento.id
        # No Client write, no estate creation, no review or knowledge promotion.
    for parte in entrada.partes:
        if parte.natureza != "espolio":
            continue
        falecido = pessoas.get(parte.falecido_chave)
        fundamento = fundamentos.get(parte.chave)
        if falecido is None or fundamento is None:
            continue  # The observation survives; insufficient basis is not an estate identity.
        row = db.query(Espolio).filter_by(tenant_id=doc.tenant_id, fundamento_id=fundamento.id).first()
        if row is None:
            # The inventory number is its own anchored observation; one link, or none.
            inventarios = [r.numero for r in entrada.referencias_processo
                           if r.sujeito == parte.chave and r.natureza == "inventario"]
            row = Espolio(tenant_id=doc.tenant_id, falecido_id=falecido.id, fundamento_id=fundamento.id,
                inventario=inventarios[0] if len(set(inventarios)) == 1 else None)
            db.add(row)
            db.flush()
        espolios[parte.chave] = row
    for ato in entrada.atos:
        if especie != "certidao_matricula" or not all((ato.rotulo, ato.matricula, ato.serventia)):
            continue  # Deed mentions remain observations; they are not registered acts.
        # Same name alone is not institutional identity. Missing CNS keeps
        # a source-scoped candidate, never a merge across unrelated registries.
        serventia = db.query(Serventia).filter_by(tenant_id=doc.tenant_id, cns=ato.cns).first() if ato.cns else (
            db.query(Serventia).filter_by(tenant_id=doc.tenant_id,
                documento_origem_id=doc.id, nome=ato.serventia).first())
        if serventia is None:
            serventia = Serventia(tenant_id=doc.tenant_id, nome=ato.serventia, cns=ato.cns, documento_origem_id=doc.id,
                motivo_cns_ausente="CNS não extraído; identidade nominal sujeita a revisão")
            db.add(serventia)
            db.flush()
        row = db.query(AtoRegistral).filter_by(tenant_id=doc.tenant_id, process_id=doc.process_id,
            serventia_id=serventia.id, matricula_numero=ato.matricula, rotulo=ato.rotulo).first()
        if row is None:
            row = AtoRegistral(tenant_id=doc.tenant_id, process_id=doc.process_id, serventia_id=serventia.id,
                matricula_numero=ato.matricula, rotulo=ato.rotulo, especie=ato.especie, natureza=ato.natureza,
                data_ato=ato.data_ato, precisao_data="dia" if ato.data_ato else "desconhecida", ordem_fonte=ato.ordem)
            db.add(row)
            db.flush()
        atos[(ato.serventia, ato.matricula, ato.rotulo)] = row
    for ato in entrada.atos:
        fundamento = fundamento_do("ato_registral", ato)
        origin = atos.get((ato.serventia, ato.matricula, ato.rotulo))
        target = atos.get((ato.serventia, ato.matricula, ato.altera_rotulo))
        if origin and target and origin.id != target.id and ato.relacao:
            if not db.query(RelacaoAto.id).filter_by(fundamento_id=fundamento.id).first():
                db.add(RelacaoAto(tenant_id=doc.tenant_id, process_id=doc.process_id,
                    origem_id=origin.id, destino_id=target.id, tipo=ato.relacao, fundamento_id=fundamento.id))
    for part in entrada.todas_participacoes:
        fundamento = fundamento_do("participacao", part)
        if db.query(Participacao.id).filter_by(tenant_id=doc.tenant_id, fundamento_id=fundamento.id).first():
            continue
        pessoa, espolio = pessoas.get(part.parte_chave), espolios.get(part.parte_chave)
        if pessoa is None and espolio is None:
            continue
        represented_person, represented_estate = pessoas.get(part.representado_chave), espolios.get(part.representado_chave)
        # A contract can name an inventariante without proving appointment,
        # scope or validity. Persist the declared role; never silently drop it
        # because the document has no cadastral destination.
        candidates = [a for a in atos.values() if a.rotulo == part.ato_rotulo]
        ato = candidates[0] if len(candidates) == 1 and part.papel not in {"inventariante", "representante"} else None
        db.add(Participacao(tenant_id=doc.tenant_id, process_id=doc.process_id,
            pessoa_id=pessoa.id if pessoa else None, espolio_id=espolio.id if espolio else None,
            ato_id=ato.id if ato else None, documento_id=None if ato else doc.id,
            papel=part.papel, estado_confirmacao="declarado", fundamento_id=fundamento.id,
            representado_pessoa_id=represented_person.id if represented_person else None,
            representado_espolio_id=represented_estate.id if represented_estate else None,
            alcance=part.alcance, inicio=part.inicio, fim=part.fim, fracao=part.fracao))
    db.flush()


def projetar_preview(rows, *, data_referencia=None):
    """Lossless multi-source display. No first-value-wins authority."""
    return {"autoridade": "projecao_de_observacoes", "observacoes": [
        {"id": r.object_id, "version": r.version, "document_id": r.source_document_id,
         "attributes": r.content["attributes"]} for r in rows],
         "qualificacao_cartoraria": qualificar_observacoes(rows, data_referencia=data_referencia)}


def qualificar_observacoes(rows, *, data_referencia):
    from app.services.motor_cartorario import (
        AtoMaterial,
        IdentidadeAto,
        avaliar_matriculas,
        qualificar_representacao,
    )
    atos, representacoes, lacunas, contextos, partes, fontes, falecimentos = [], [], [], {}, [], {}, []
    for row in rows:
        metadata = row.source_record or {}
        item = row.content["attributes"].get("normalized") or {}
        if not isinstance(item, dict):
            continue
        especie = metadata.get("especie_documental", "indeterminada")
        fontes[row.source_document_id] = {"documento_id": row.source_document_id,
            "especie": especie, "sustenta": SUPORTE[especie]}
        if metadata.get("tipo_entrada") == "parte":
            partes.append({"observacao": row.object_id, "documento_id": row.source_document_id,
                "estado_confirmacao": "declarado", **item})
        if metadata.get("tipo_entrada") == "falecimento_declarado":
            falecimentos.append({"observacao": row.object_id, "versao": row.version,
                "documento_id": row.source_document_id, **item,
                "estado_pessoa": "falecimento_declarado", "suficiencia_gate": "PENDENTE-ISIS"})
            sem_suporte = {c["campo"] for c in item.get("campos_sem_suporte", [])}
            for campo in ("ano", "data_consulta"):
                if item.get(campo) is None:
                    motivo = "sem_suporte_no_trecho" if campo in sem_suporte else "nao_localizado_no_material"
                    lacunas.append({"observacao": row.object_id, "motivo": f"{campo}_{motivo}"})
        if metadata.get("tipo_entrada") == "ato_registral":
            if not all(item.get(k) for k in ("serventia", "matricula", "rotulo")):
                lacunas.append({"observacao": row.object_id, "motivo": "identidade_registral_nao_determinada",
                    "suporte": SUPORTE[especie]})
                continue
            identidade = IdentidadeAto(row.source_document_id, item["matricula"], item["serventia"], item["rotulo"])
            alvo = IdentidadeAto(row.source_document_id, item["matricula"], item["serventia"], item["altera_rotulo"]) if item.get("altera_rotulo") else None
            atos.append(AtoMaterial(identidade, item["natureza"],
                date.fromisoformat(item["data_ato"]) if item.get("data_ato") else None,
                item["ordem"], alvo=alvo, relacao=item.get("relacao")))
            key = (identidade.serventia, identidade.matricula)
            previous = contextos.get(key)
            contextos[key] = {"especie": especie if previous is None or previous["especie"] == especie else "indeterminada"}
        if metadata.get("tipo_entrada") == "participacao" and item.get("papel") in {"representante", "inventariante"}:
            representacoes.append({"observacao": row.object_id, "documento_id": row.source_document_id,
                "papel": item["papel"], **qualificar_representacao(especie=especie,
                    alcance=item.get("alcance"), inicio=date.fromisoformat(item["inicio"]) if item.get("inicio") else None,
                    fim=date.fromisoformat(item["fim"]) if item.get("fim") else None,
                    representado=item.get("representado_chave"), data_referencia=data_referencia)})
    if data_referencia is None:
        lacunas.append({"motivo": "data_de_referencia_nao_determinada"})
    return {"matriculas": avaliar_matriculas(atos=atos, data_referencia=data_referencia,
        contexto_por_matricula=contextos) if data_referencia else [],
        "representacoes": representacoes, "partes": partes, "fontes": list(fontes.values()), "lacunas": lacunas,
        "falecimentos_declarados": falecimentos,
        "limites": ["Participações extraídas são declarações; cadeia completa e poderes dependem de fundamento e revisão."]}


ITENS = {"partes": ParteExtraida, "participacoes": ParticipacaoExtraida, "atos": AtoExtraido,
         "observacoes": ObservacaoExtraida, "contratos": ContratoExtraido,
         "falecimentos_declarados": FalecimentoDeclarado, "referencias_processo": ReferenciaProcesso}
ESPECIES_CONTRATUAIS = {"contrato_particular", "contrato_servico_documental"}
RECEITA = "comprovante_situacao_cadastral_cpf"


def _sem_espacos(valor):
    return re.sub(r"\s+", "", valor)


def _motivo_schema(exc):
    # Messages only: Pydantic input values would copy source text into the rejection record.
    return "; ".join(f"{'.'.join(map(str, e['loc'])) or 'item'}: {e['msg']}"
                     for e in exc.errors(include_url=False, include_input=False))


def _posicoes(item):
    valores = item if isinstance(item, dict) else getattr(item, "__dict__", {})
    return {campo: valores.get(campo) if isinstance(valores.get(campo), int) else None
            for campo in ("posicao_inicio", "posicao_fim")}


def _ancorar(item, nome, texto, inicio_fatia, fim_fatia, especie):
    """Checks local to one proposed item; the ValueError message is the rejection reason.

    A resolved anchor is the condition for the observation to enter. A field the
    item's own anchor does not support is emptied with its reason and knowledge
    not determined (André, 21/09/2026); the observation stays.
    """
    literal, start = resolver_ancora_literal(texto, item.trecho, item.posicao_inicio, item.posicao_fim)
    end = start + len(literal)
    if start < inicio_fatia or end > fim_fatia:
        raise ValueError("Ancora fora da fatia examinada")
    item.trecho, item.posicao_inicio, item.posicao_fim = literal, start, end
    if especie and nome == "contratos" and especie not in ESPECIES_CONTRATUAIS:
        raise ValueError("Objeto contratual não sustentado pela espécie documental")
    if especie and nome == "falecimentos_declarados" and especie != RECEITA:
        raise ValueError("Declaração de falecimento exige a espécie Receita")
    if especie == RECEITA and (nome == "participacoes" or (nome == "partes" and item.natureza == "espolio")):
        raise ValueError("Receita não fundamenta espólio ou representação")
    if nome == "referencias_processo":
        # The number is what this observation asserts: without it in the anchor there is no observation.
        if especie and especie not in ESPECIES_CONTRATUAIS:
            raise ValueError("Referência a processo fora da família contratual")
        if _sem_espacos(item.numero) not in _sem_espacos(literal):
            raise ValueError("Número do processo ausente do trecho")
    if nome == "falecimentos_declarados" and "titular falecido" not in literal.lower():
        raise ValueError("Falecimento declarado exige trecho TITULAR FALECIDO")
    compacto = _sem_espacos(literal)

    def sem_suporte(campo, motivo):
        item._campos_sem_suporte.append({"campo": campo, "motivo": motivo, "conhecimento": "nao_determinado"})

    if nome == "partes" and item.identificador and _sem_espacos(item.identificador) not in compacto:
        sem_suporte("identificador", "Identificador ausente do trecho da parte")
        item.identificador = item.tipo_identificador = None  # the schema keeps value and type together
    if nome == "falecimentos_declarados":
        if item.ano is not None and not re.search(rf"\b{item.ano}\b", literal):
            sem_suporte("ano", "Ano de falecimento ausente do trecho")
            item.ano = None
        consulta = item.data_consulta
        if consulta and not any(v in literal for v in (consulta.isoformat(), consulta.strftime("%d/%m/%Y"))):
            sem_suporte("data_consulta", "Data da consulta ausente do trecho")
            item.data_consulta = None


def validar_proposta(proposta, texto, inicio_fatia, fim_fatia, *, especie=None):
    """Validate each proposed item; one invalid item never discards the others.

    Schema, anchor, species and literal support are checked per item. A reference
    to an absent or rejected party rejects only the dependent claim. Indices point
    into the proposal, whose raw response stays in the job audit. Only a response
    that is not a JSON object fails whole.
    """
    if not isinstance(proposta, dict):
        raise ValueError("Resposta do extrator não é objeto JSON")
    rejeicoes = []

    def rejeitar(colecao, indice, item, motivo):
        rejeicoes.append({"colecao": colecao, "indice": indice, "motivo": motivo, **_posicoes(item)})

    def validar(colecao, nome, modelo, indice, bruto):
        try:
            item = modelo.model_validate(bruto)
            _ancorar(item, nome, texto, inicio_fatia, fim_fatia, especie)
        except ValidationError as exc:
            rejeitar(colecao, indice, bruto, _motivo_schema(exc))
        except ValueError as exc:
            rejeitar(colecao, indice, bruto, str(exc))
        else:
            for campo in item._campos_sem_suporte:
                campo.update(colecao=colecao, indice=indice)
            return item

    for nome in sorted(proposta.keys() - EntradaExtraida.model_fields.keys()):
        rejeitar(nome, None, None, "Coleção fora do schema")
    try:
        limites = TypeAdapter(list[str]).validate_python(proposta.get("limites") or [])
    except ValidationError as exc:
        limites = []
        rejeitar("limites", None, None, _motivo_schema(exc))
    itens, representacoes = {}, {}
    for nome, modelo in ITENS.items():
        brutos = proposta.get(nome)
        itens[nome] = []
        if brutos is None:
            continue
        if not isinstance(brutos, list):
            rejeitar(nome, None, None, "Coleção deve ser lista")
            continue
        for indice, bruto in enumerate(brutos):
            if nome == "contratos" and isinstance(bruto, dict) and isinstance(
                    reps := bruto.get("representacao_declarada") or [], list):
                # Each declared representation stands alone, like any participation.
                colecao = f"contratos[{indice}].representacao_declarada"
                representacoes[indice] = []
                for j, rep in enumerate(reps):
                    item = validar(colecao, "participacoes", ParticipacaoExtraida, j, rep)
                    if item is not None and item.papel not in {"representante", "inventariante"}:
                        rejeitar(colecao, j, rep, "Representação contratual exige papel representante ou inventariante")
                    elif item is not None:
                        representacoes[indice].append((j, item))
                bruto = {**bruto, "representacao_declarada": []}
            if (item := validar(nome, nome, modelo, indice, bruto)) is not None:
                itens[nome].append((indice, item))

    brutas = proposta.get("partes")
    chaves_propostas = {p.get("chave") for p in brutas if isinstance(p, dict)} if isinstance(brutas, list) else set()

    def referencia(chave, aceitas, existentes, motivo):
        if chave in aceitas:
            return None
        return "Dependência de parte rejeitada" if chave in chaves_propostas and chave not in existentes else motivo

    # A rejected identity cannot become the foundation of another accepted claim.
    while True:
        contagem = Counter(p.chave for _, p in itens["partes"])
        unicas = {chave for chave, n in contagem.items() if n == 1}
        pf = {p.chave for _, p in itens["partes"] if p.chave in unicas and p.natureza == "pf"}
        invalidas = {}
        for indice, parte in itens["partes"]:
            if parte.chave not in unicas:
                invalidas[indice] = "Chave de parte duplicada no documento"
            elif parte.natureza == "espolio" and (motivo := referencia(parte.falecido_chave, pf, unicas,
                    "Espólio exige referência à pessoa física falecida")):
                invalidas[indice] = motivo
        if not invalidas:
            break
        for indice, parte in itens["partes"]:
            if indice in invalidas:
                rejeitar("partes", indice, parte, invalidas[indice])
        itens["partes"] = [(i, p) for i, p in itens["partes"] if i not in invalidas]
    chaves = {p.chave for _, p in itens["partes"]}

    def participacao(p):
        return referencia(p.parte_chave, chaves, chaves, "Participação sem parte extraída") or (
            p.representado_chave and referencia(p.representado_chave, chaves, chaves, "Representado sem parte extraída"))

    def manter(colecao, pares, motivo):
        mantidos = []
        for indice, item in pares:
            if razao := motivo(item):
                rejeitar(colecao, indice, item, razao)
            else:
                mantidos.append((indice, item))
        return mantidos

    itens["participacoes"] = manter("participacoes", itens["participacoes"], participacao)
    itens["falecimentos_declarados"] = manter("falecimentos_declarados", itens["falecimentos_declarados"],
        lambda f: referencia(f.sujeito, pf, chaves, "Falecimento declarado exige sujeito pessoa física, não espólio"))
    itens["observacoes"] = manter("observacoes", itens["observacoes"], lambda o:
        "Use falecimentos_declarados para respeitar o schema e os limites da fonte"
        if o.predicado == "falecimento_declarado" else
        "Dependência de parte rejeitada" if o.sujeito in chaves_propostas - chaves else None)

    def partes_contratuais(c):
        return next((m for k in [*c.contratante, *c.contratado]
                     if (m := referencia(k, chaves, chaves, "Parte contratual sem identidade extraída"))), None)

    itens["contratos"] = manter("contratos", itens["contratos"], partes_contratuais)
    itens["referencias_processo"] = manter("referencias_processo", itens["referencias_processo"], lambda r:
        r.sujeito and referencia(r.sujeito, chaves, chaves, "Referência a processo vinculada a parte sem identidade extraída"))
    for indice, contrato in itens["contratos"]:
        contrato.representacao_declarada = [item for _, item in manter(
            f"contratos[{indice}].representacao_declarada", representacoes.get(indice, []), participacao)]
    return EntradaExtraida(limites=limites, **{nome: [item for _, item in pares] for nome, pares in itens.items()}), rejeicoes


DEPENDENCIA = "Dependência de parte rejeitada"
INSTRUCAO_REPARO = (
    "\nRODADA DE REPARO (uma tentativa). Os itens abaixo foram rejeitados na validação, cada um com "
    "o motivo. Para cada um, devolva o item corrigido conforme o schema: trecho copiado do texto "
    "caractere por caractere, contíguo, sem reescrever, resumir, pular ou juntar pedaços; se o trecho se "
    "repete, amplie-o até ser único ou informe offsets exatos. Quando houver 'divergencia', seu trecho "
    "coincide com a fonte nas primeiras palavras indicadas e depois a fonte segue com 'fonte_continua': "
    "copie essa continuação ou termine o trecho no ponto de divergência. Se o texto não sustenta o item, "
    "devolva item null. Não altere nem acrescente outros itens. Responda só JSON, sem Markdown: "
    '{"reparos": [{"colecao": ..., "indice": ..., "item": {...} ou null}]}.\nItens rejeitados: ')


def divergencia(texto, trecho, janela=60):
    """Where a non-existent anchor departs from the source, for the repair round.

    The longest prefix of the anchor (whitespace-tolerant, as the resolver) found in the
    source; the source and the anchor continuations show the model what it skipped or
    rewrote. On 21/09/2026 the model jumped a 176-character control code to reach a date.
    """
    tokens = trecho.split()

    def busca(n):
        return re.search(r"\s+".join(re.escape(t) for t in tokens[:n]), texto) if n else None
    baixo, alto = 0, len(tokens)
    while baixo < alto:  # a prefix that matches implies every shorter one matches
        meio = (baixo + alto + 1) // 2
        baixo, alto = (meio, alto) if busca(meio) else (baixo, meio - 1)
    if not baixo:
        return {"coincide_palavras": 0, "total_palavras": len(tokens)}
    fim = busca(baixo).end()
    return {"coincide_palavras": baixo, "total_palavras": len(tokens),
            "fonte_continua": texto[fim:fim + janela], "trecho_continua": " ".join(tokens[baixo:])[:janela]}


def _item_da_proposta(proposta, colecao, indice):
    if "[" in colecao:  # contratos[i].representacao_declarada
        contrato = int(colecao.split("[")[1].split("]")[0])
        return proposta["contratos"][contrato]["representacao_declarada"], indice
    return proposta[colecao], indice


def reparar_proposta(proposta, recusadas, pedir, texto=None):
    """One repair round: each item rejected on its own checks returns to the model with its reason.

    Dependency rejections are not sent: a repaired parent clears them on revalidation. Returns the
    proposal with repaired items in their original places (to revalidate as a whole) and the
    request list. ``pedir`` returns the parsed {"reparos": [...]} or raises ValueError.
    """
    pedidos = []
    for r in recusadas:
        if r["indice"] is None or r["motivo"] == DEPENDENCIA:
            continue
        lista, indice = _item_da_proposta(proposta, r["colecao"], r["indice"])
        pedido = {"colecao": r["colecao"], "indice": indice, "motivo": r["motivo"], "item": lista[indice]}
        trecho = lista[indice].get("trecho") if isinstance(lista[indice], dict) else None
        if texto and isinstance(trecho, str) and "não existe" in r["motivo"]:
            pedido["divergencia"] = divergencia(texto, trecho)
        pedidos.append(pedido)
    if not pedidos:
        return proposta, []
    resposta = pedir(pedidos)
    reparada = json.loads(json.dumps(proposta))
    solicitados = {(p["colecao"], p["indice"]) for p in pedidos}
    devolvidos = set()
    for reparo in (resposta.get("reparos") if isinstance(resposta, dict) else None) or []:
        chave = (reparo.get("colecao"), reparo.get("indice")) if isinstance(reparo, dict) else None
        if chave in solicitados and isinstance(reparo.get("item"), dict):
            lista, indice = _item_da_proposta(reparada, *chave)
            lista[indice] = reparo["item"]
            devolvidos.add(chave)
    for pedido in pedidos:
        pedido["devolvido"] = (pedido["colecao"], pedido["indice"]) in devolvidos
    return reparada, pedidos


def registro_do_reparo(pedidos, recusadas_finais):
    finais = {(r["colecao"], r["indice"]): r["motivo"] for r in recusadas_finais}
    registro = []
    for pedido in pedidos:
        chave = (pedido["colecao"], pedido["indice"])
        resultado = ("nao_devolvido" if not pedido["devolvido"] else
                     "rejeitado" if chave in finais else "aceito")
        registro.append({"colecao": pedido["colecao"], "indice": pedido["indice"],
                         "motivo_original": pedido["motivo"], "resultado": resultado,
                         **({"motivo_final": finais[chave]} if chave in finais else {})})
    return registro


def extrair_documento(db, doc, *, manifest, on_response=None, superacoes=None):
    """Único parser/persistidor, compartilhado pelo agente e adaptador de staging.

    With ``superacoes`` the caller supersedes the previous version after writing
    the case derivations; otherwise supersession happens here.
    """
    from app.core.ai_gateway import AIGatewayError, complete
    from app.services.taxonomia_documental import FAMILIAS
    if manifest["status"] != "available":
        raise HTTPException(422, "Capacidade insuficiente: método obrigatório indisponível")
    classification = classificacao_atual(db, doc)
    especie = (classification.tipo_revisado or classification.tipo_proposto) if classification else propor_especie(
        doc.extracted_text, doc.document_type)
    family = FAMILIAS.get(especie)
    if family is None:
        raise HTTPException(422, "Espécie não determinada; revisar classificação antes de extrair")
    if doc.source == DocumentSource.generated_ai:
        raise HTTPException(422, "Saída de IA não é fonte primária de extração")
    system = "\n\n".join(s["content"] for s in manifest["applied"] if s["name"] == f"extrator/{family}")
    if not system:
        raise HTTPException(422, "Capacidade insuficiente: método da família indisponível")
    system += "\nProduza JSON conforme o schema, com trechos literais exatos. Não invente papel, data ou fração.\n"
    system += json.dumps(EntradaExtraida.model_json_schema(), ensure_ascii=False)
    from app.core.config import settings
    from app.services.extraction_window import fatiar
    fatias = fatiar(doc.extracted_text, chunk_chars=settings.EXTRACTOR_CHUNK_CHARS,
        overlap_chars=settings.EXTRACTOR_CHUNK_OVERLAP_CHARS, max_chunks=settings.EXTRACTOR_MAX_CHUNKS)
    if not fatias or fatias[-1].fim != len(doc.extracted_text):
        raise HTTPException(422, "Cobertura documental insuficiente; nenhuma extração parcial será publicada como completa")
    colecoes = {key: [] for key in EntradaExtraida.model_fields}
    modelos = []
    rejeicoes, campos, reparos = [], [], []
    for fatia in fatias:
        texto = doc.extracted_text[fatia.inicio:fatia.fim]
        system_fatia = system + (f"\nEspécie: {especie}. Fatia {fatia.indice}; "
            f"Offsets globais em caracteres Unicode no extracted_text; fatia [{fatia.inicio}, {fatia.fim}). "
            "Informe posicao_inicio (start, base zero) e posicao_fim (end exclusivo) além do literal. "
            "Para trecho único, offsets podem ser nulos e serão localizados deterministicamente. "
            "Trecho repetido exige offsets corretos; sem eles somente a observação será rejeitada. "
            "Não estime offsets. Amplie o trecho para torná-lo único quando necessário. "
            "Não preencha campos de famílias ausentes. Não devolva Markdown.")

        def chamar(sistema, rotulo, texto=texto):
            response = complete(texto, system=sistema, agent_name="extrator", model=settings.AI_EXTRATOR_MODEL,
                allow_fallback=settings.AI_EXTRATOR_ALLOW_FALLBACK, max_tokens=12000, temperature=0)
            if on_response:
                on_response(response, rotulo)
            modelos.append(response.model_used)
            raw = response.content.strip()
            if raw.startswith("```"):
                raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw)
            try:
                return json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Resposta do extrator não é JSON: {exc.msg}") from exc

        proposta = chamar(system_fatia, f"doc{doc.id}:{fatia.rotulo}")
        parcial, recusadas = validar_proposta(proposta, doc.extracted_text, fatia.inicio, fatia.fim, especie=especie)
        # Skill compensation (André, 21/09/2026): one repair round, result recorded per item.
        try:
            reparada, pedidos = reparar_proposta(proposta, recusadas, lambda itens, sistema=system_fatia,
                rotulo=f"doc{doc.id}:{fatia.rotulo}:reparo": chamar(
                    sistema + INSTRUCAO_REPARO + json.dumps(itens, ensure_ascii=False), rotulo), texto=texto)
        except (ValueError, AIGatewayError) as exc:
            reparos.append({"fatia": fatia.indice, "erro": getattr(exc, "message", None) or str(exc)})
        else:
            if pedidos:
                parcial, recusadas = validar_proposta(reparada, doc.extracted_text, fatia.inicio, fatia.fim,
                                                      especie=especie)
                reparos.extend({**r, "fatia": fatia.indice} for r in registro_do_reparo(pedidos, recusadas))
        rejeicoes.extend({**r, "fatia": fatia.indice} for r in recusadas)
        for campo in campos_sem_suporte(parcial):
            campo["fatia"] = fatia.indice
            campos.append(campo)
        # Window-local references remain scoped; same names never merge identities.
        prefix = f"f{fatia.indice}:"
        for parte in parcial.partes:
            parte.chave = prefix + parte.chave
            if parte.falecido_chave:
                parte.falecido_chave = prefix + parte.falecido_chave
        for part in parcial.todas_participacoes:
            part.parte_chave = prefix + part.parte_chave
            if part.representado_chave:
                part.representado_chave = prefix + part.representado_chave
        for contrato in parcial.contratos:
            contrato.contratante = [prefix + key for key in contrato.contratante]
            contrato.contratado = [prefix + key for key in contrato.contratado]
        for declaracao in parcial.falecimentos_declarados:
            declaracao.sujeito = prefix + declaracao.sujeito
        for referencia in parcial.referencias_processo:
            if referencia.sujeito:
                referencia.sujeito = prefix + referencia.sujeito
        for key in colecoes:
            colecoes[key].extend(getattr(parcial, key))
    entrada = EntradaExtraida(**colecoes)
    if family == "contratual" and not entrada.contratos and not rejeicoes:
        raise HTTPException(422, "Extração contratual incompleta: contratos ausentes; não publicar sucesso vazio")
    if especie == "comprovante_situacao_cadastral_cpf" and "titular falecido" in doc.extracted_text.lower() and not entrada.falecimentos_declarados and not rejeicoes:
        raise HTTPException(422, "Extração cadastral incompleta: declaração de falecimento não preservada")
    rows = persistir_entrada(db, doc, entrada, modelo=",".join(sorted(set(modelos))))
    anteriores = extracao_anterior(db, doc, {r.id for r in rows})
    source = fonte_documental(db, doc)
    # One version per extraction of the document: its observations and what it supersedes.
    relatorio = _capture(db, doc.tenant_id, doc.process_id, f"extracao:rejeicoes:{doc.id}", "derivacao", {
            "origin": "extrator", "attributes": {"document_id": doc.id, "method": "validacao_ancoras", "method_version": "071.3",
                "normalized": {"rejeicoes": rejeicoes, "campos_sem_suporte": campos, "reparos": reparos,
                    "observacoes_preservadas": len(rows),
                    "observacoes": [{"id": r.object_id, "version": r.version} for r in rows],
                    "superadas": [{"id": r.object_id, "version": r.version} for r in anteriores]}},
            "premises": [{"id": source.object_id, "version": source.version}],
            "limits": ["Extracao parcial: observacoes rejeitadas exigem revisao."] if rejeicoes else [],
        })
    if superacoes is None:
        superar(db, doc, anteriores, relatorio)
    else:
        superacoes.append((doc, anteriores, relatorio))
    doc.review_required = doc.review_required or bool(rows) or bool(rejeicoes) or bool(campos)
    doc.extraction_status = "observações extraídas; revisão necessária" if rows else "extração sem observações"
    if rejeicoes or campos:
        doc.extraction_status = (f"extracao parcial: {len(rows)} preservadas; {len(rejeicoes)} rejeitadas por "
                                 f"ancora/dependencia; {len(campos)} campos sem suporte no trecho; revisar")
    return rows


def extracao_anterior(db, doc, atuais):
    """Current semantic observations of the document that the new extraction did not produce again.

    An observation a consultant decided (review in the panel, or an accepted or
    rejected projection) is not the machine's to supersede; it stays as decided.
    """
    invalid = {i.evidence_id for i in db.query(EvidenceInvalidation).filter(
        EvidenceInvalidation.tenant_id == doc.tenant_id, EvidenceInvalidation.process_id == doc.process_id)}
    decididas = set(reviews_by_evidence(db, doc.tenant_id, doc.process_id))
    decididas |= {ref for (ref,) in db.query(ExtractedFieldStaging.observacao_ref).filter(
        ExtractedFieldStaging.tenant_id == doc.tenant_id, ExtractedFieldStaging.process_id == doc.process_id,
        ExtractedFieldStaging.observacao_ref.isnot(None),
        (ExtractedFieldStaging.decided_by_user_id.isnot(None)) | ExtractedFieldStaging.status.in_(
            [ExtractedFieldStatus.aceito, ExtractedFieldStatus.rejeitado]))}
    return [r for r in latest_objects(db, doc.tenant_id, doc.process_id).values()
            if r.kind == "observacao" and r.source_document_id == doc.id and r.id not in atuais
            and r.id not in invalid and r.id not in decididas
            and r.content["attributes"].get("method") == "extrator_semantico"]


def superar(db, doc, anteriores, relatorio):
    """ADR-070: re-extraction is a new version; the previous one is superseded, never erased.

    The single invalidation mechanism takes superseded observations out of the
    envelope and invalidates their dependents. Their undecided review projections
    leave the queue: they are projections, and the observation keeps the history.
    """
    if not anteriores:
        return
    motivo = {"superada_por": {"id": relatorio.object_id, "version": relatorio.version},
              "motivo": "nova extração do documento"}
    for row in anteriores:
        db.add(EvidenceInvalidation(tenant_id=doc.tenant_id, process_id=doc.process_id, evidence_id=row.id, reason=motivo))
    for staging in db.query(ExtractedFieldStaging).filter(ExtractedFieldStaging.tenant_id == doc.tenant_id,
            ExtractedFieldStaging.observacao_ref.in_([r.id for r in anteriores])):
        if staging.decided_by_user_id is None and staging.status not in (
                ExtractedFieldStatus.aceito, ExtractedFieldStatus.rejeitado):
            db.delete(staging)
    db.flush()
    invalidate_dependents(db, doc.tenant_id, doc.process_id)


def executar_extracao(ctx, *, on_response=None, ai_job_id=None):
    from app.services.agent_capabilities import capability_manifest
    if ctx.process_id is None:
        return {"skipped": True, "reason": "Informe process_id e document_id; use POST /processes/{id}/extract"}
    authorize(ctx.session, ctx.tenant_id, ctx.user_id, ctx.process_id)
    manifest = capability_manifest("extrator", ctx.metadata)
    if manifest["status"] != "available":
        return {"status": "capacidade_insuficiente", "manifest": manifest}
    query = ctx.session.query(Document).filter_by(tenant_id=ctx.tenant_id, process_id=ctx.process_id,
        deleted_at=None).filter((Document.source.is_(None)) | (Document.source != DocumentSource.generated_ai))
    if ctx.metadata.get("document_id"):
        query = query.filter(Document.id == ctx.metadata["document_id"])
    rows, documentos_sem_texto, superacoes = [], [], []
    for doc in query.order_by(Document.id).all():
        if not (doc.extracted_text or "").strip() and ctx.metadata.get("document_id") == doc.id and ctx.metadata.get("text"):
            from datetime import UTC, datetime
            # Compatibility input is persisted once; the observation parser reads only the document.
            doc.extracted_text = ctx.metadata["text"]
            doc.extracted_at = datetime.now(UTC)
            ctx.session.flush()
        if not (doc.extracted_text or "").strip():
            documentos_sem_texto.append({"documento_id": doc.id, "motivo": "texto_ausente"})
            continue
        rows.extend(extrair_documento(ctx.session, doc, manifest=manifest, on_response=on_response,
                                      superacoes=superacoes))
    if not rows and documentos_sem_texto:
        raise ValueError("OCR: texto extraido ausente; reprocessar os documentos antes de extrair")
    if ai_job_id is not None and rows:
        for staging in ctx.session.query(ExtractedFieldStaging).filter(
                ExtractedFieldStaging.tenant_id == ctx.tenant_id,
                ExtractedFieldStaging.observacao_ref.in_([r.id for r in rows]),
                ExtractedFieldStaging.ai_job_id.is_(None)):
            staging.ai_job_id = ai_job_id
        ctx.session.flush()
    from app.services.ficha01_extraction import data_referencia_do_processo
    reference = data_referencia_do_processo(ctx.session, ctx.tenant_id, ctx.process_id)
    preview = projetar_preview(rows, data_referencia=reference)
    if rows:
        derivacao = _capture(ctx.session, ctx.tenant_id, ctx.process_id, "cartorario:material", "derivacao", {
            "origin": "motor_cartorario", "attributes": {"method": "cartorario", "method_version": "071.1",
                "reference_date": reference.isoformat() if reference else None,
                "normalized": preview["qualificacao_cartoraria"]},
            "premises": [{"id": r.object_id, "version": r.version} for r in rows],
            "limits": ["Qualificação do material; não certifica titularidade atual ou poderes externos."],
        })
        preview["derivacao_cartoraria"] = {"id": derivacao.object_id, "version": derivacao.version}
    # After the new derivation: its previous version is superseded by version, not a pendency.
    for superacao in superacoes:
        superar(ctx.session, *superacao)
    return {**preview, "manifest": manifest, "documentos_sem_texto": documentos_sem_texto,
        "pendencias_dominio": ["PENDENTE-ISIS: suficiência da Receita para o gate de falecimento"]
            if preview["qualificacao_cartoraria"]["falecimentos_declarados"] else [],
        "requires_review": bool(rows)}
