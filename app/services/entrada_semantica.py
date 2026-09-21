"""Entrada única: fonte versionada → observação durável → projeção de staging."""
import json
import re
from datetime import date

from fastapi import HTTPException

from app.models.document import Document, DocumentSource
from app.models.entrada_semantica import ClassificacaoDocumento, DocumentoVersao
from app.models.extracted_field_staging import ExtractedFieldStaging, ExtractedFieldStatus
from app.schemas.entrada_semantica import EntradaExtraida, EspecieDocumental
from app.schemas.evidence import EvidenceAttributes, EvidenceRef
from app.services.documento_versao import registrar_fragmento, registrar_leitura
from app.services.evidence import _capture, authorize, lock_case
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
    items = [("parte", x.model_dump(mode="json"), x.trecho) for x in entrada.partes]
    items += [("observacao", x.model_dump(mode="json"), x.trecho) for x in entrada.observacoes]
    items += [("ato_registral", x.model_dump(mode="json"), x.trecho) for x in entrada.atos]
    items += [("participacao", x.model_dump(mode="json"), x.trecho) for x in entrada.todas_participacoes]
    items += [("contrato", {**x.model_dump(mode="json"), "predicado": especie}, x.trecho) for x in entrada.contratos]
    items += [("falecimento_declarado", x.model_dump(mode="json"), x.trecho) for x in entrada.falecimentos_declarados]
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
            if any(re.sub(r"\s+", "", numero) not in re.sub(r"\s+", "", trecho)
                   for numero in item["referencia_processo_judicial"]):
                raise HTTPException(422, "Referência judicial ausente do trecho contratual")
            for representacao in item["representacao_declarada"]:
                representacao["estado_confirmacao"] = "declarado"
            item["lacunas"] = [campo for campo in ("contratante", "contratado", "objeto") if not item[campo]]
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
        sem_destino = tipo in {"parte", "participacao", "contrato", "ato_registral", "falecimento_declarado"}
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
        normalized = normalizar_conteudo(item.model_dump(mode="json"))
        if tipo == "participacao":
            normalized["estado_confirmacao"] = "declarado"
        matches = [r for r in refs if (r.source_record or {}).get("tipo_entrada") == tipo
                   and r.content["attributes"]["normalized"] == normalized]
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
            if parte.inventario and re.sub(r"\s+", "", parte.inventario) not in re.sub(r"\s+", "", parte.trecho):
                raise HTTPException(422, "Número de inventário não localizado no documento")
            row = Espolio(tenant_id=doc.tenant_id, falecido_id=falecido.id,
                fundamento_id=fundamento.id, inventario=parte.inventario)
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
            for campo in ("ano", "data_consulta"):
                if item.get(campo) is None:
                    lacunas.append({"observacao": row.object_id, "motivo": f"{campo}_nao_localizado_no_material"})
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



def filtrar_ancoras(entrada, texto, inicio_fatia, fim_fatia):
    """Reject individual invalid anchors and dependent claims, retaining independent items."""
    rejeicoes = []
    def rejeitar(colecao, indice, item, motivo):
        rejeicoes.append({"colecao": colecao, "indice": indice, "motivo": motivo,
            "posicao_inicio": item.posicao_inicio, "posicao_fim": item.posicao_fim})
    def filtrar(items, nome):
        validos = []
        for indice, item in enumerate(items):
            try:
                if item.posicao_inicio is None and item.posicao_fim is None:
                    literal, start = resolver_ancora_literal(texto, item.trecho)
                else:
                    literal, start = resolver_ancora_literal(texto, item.trecho, item.posicao_inicio, item.posicao_fim)
                end = start + len(literal)
                if start < inicio_fatia or end > fim_fatia:
                    raise ValueError("Ancora fora da fatia examinada")
                item.trecho, item.posicao_inicio, item.posicao_fim = literal, start, end
                validos.append(item)
            except ValueError as exc:
                rejeitar(nome, indice, item, str(exc))
        return validos
    nomes = ("partes", "participacoes", "atos", "observacoes", "contratos", "falecimentos_declarados")
    originais = {p.chave for p in entrada.partes}
    for nome in nomes:
        setattr(entrada, nome, filtrar(getattr(entrada, nome), nome))
    for i, contrato in enumerate(entrada.contratos):
        contrato.representacao_declarada = filtrar(contrato.representacao_declarada, f"contratos[{i}].representacao_declarada")
    # A rejected identity cannot become the foundation of another accepted claim.
    while True:
        chaves = {p.chave for p in entrada.partes}
        invalidas = [p for p in entrada.partes if p.falecido_chave and p.falecido_chave not in chaves]
        if not invalidas:
            break
        for p in invalidas:
            rejeitar("partes", entrada.partes.index(p), p, "Dependencia de parte rejeitada")
            entrada.partes.remove(p)
    perdidas = originais - {p.chave for p in entrada.partes}
    def dependencias(item):
        return [getattr(item, key, None) for key in ("parte_chave", "representado_chave", "sujeito")]
    def manter(items, nome):
        validos = []
        for i, item in enumerate(items):
            deps = dependencias(item)
            if nome == "contratos":
                deps += item.contratante + item.contratado
            if any(d in perdidas for d in deps):
                rejeitar(nome, i, item, "Dependencia de parte rejeitada")
            else:
                validos.append(item)
        return validos
    for nome in ("participacoes", "observacoes", "falecimentos_declarados", "contratos"):
        setattr(entrada, nome, manter(getattr(entrada, nome), nome))
    for contrato in entrada.contratos:
        contrato.representacao_declarada = manter(contrato.representacao_declarada, "representacao_declarada")
    return entrada, rejeicoes


def extrair_documento(db, doc, *, manifest, on_response=None):
    """Único parser/persistidor, compartilhado pelo agente e adaptador de staging."""
    from app.core.ai_gateway import complete
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
    rejeicoes = []
    for fatia in fatias:
        texto = doc.extracted_text[fatia.inicio:fatia.fim]
        response = complete(texto, system=system + f"\nEspécie: {especie}. Fatia {fatia.indice}; "
            f"Offsets globais em caracteres Unicode no extracted_text; fatia [{fatia.inicio}, {fatia.fim}). "
            "Informe posicao_inicio (start, base zero) e posicao_fim (end exclusivo) além do literal. "
            "Para trecho único, offsets podem ser nulos e serão localizados deterministicamente. "
            "Trecho repetido exige offsets corretos; sem eles somente a observação será rejeitada. "
            "Não estime offsets. Amplie o trecho para torná-lo único quando necessário. "
            "Não preencha campos de famílias ausentes. Não devolva Markdown.",
            agent_name="extrator", model=settings.AI_EXTRATOR_MODEL, allow_fallback=settings.AI_EXTRATOR_ALLOW_FALLBACK,
            max_tokens=12000, temperature=0)
        if on_response:
            on_response(response, f"doc{doc.id}:{fatia.rotulo}")
        raw = response.content.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw)
        parcial = EntradaExtraida.model_validate_json(raw)
        parcial, recusadas = filtrar_ancoras(parcial, doc.extracted_text, fatia.inicio, fatia.fim)
        rejeicoes.extend({**r, "fatia": fatia.indice} for r in recusadas)
        modelos.append(response.model_used)
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
        for key in colecoes:
            colecoes[key].extend(getattr(parcial, key))
    entrada = EntradaExtraida(**colecoes)
    if family == "contratual" and not entrada.contratos and not rejeicoes:
        raise HTTPException(422, "Extração contratual incompleta: contratos ausentes; não publicar sucesso vazio")
    if especie == "comprovante_situacao_cadastral_cpf" and "titular falecido" in doc.extracted_text.lower() and not entrada.falecimentos_declarados and not rejeicoes:
        raise HTTPException(422, "Extração cadastral incompleta: declaração de falecimento não preservada")
    rows = persistir_entrada(db, doc, entrada, modelo=",".join(sorted(set(modelos))))
    source = fonte_documental(db, doc)
    _capture(db, doc.tenant_id, doc.process_id, f"extracao:rejeicoes:{doc.id}", "derivacao", {
            "origin": "extrator", "attributes": {"document_id": doc.id, "method": "validacao_ancoras", "method_version": "071.2",
                "normalized": {"rejeicoes": rejeicoes, "observacoes_preservadas": len(rows)}},
            "premises": [{"id": source.object_id, "version": source.version}],
            "limits": ["Extracao parcial: observacoes rejeitadas exigem revisao."] if rejeicoes else [],
        })
    doc.review_required = doc.review_required or bool(rows) or bool(rejeicoes)
    doc.extraction_status = "observações extraídas; revisão necessária" if rows else "extração sem observações"
    if rejeicoes:
        doc.extraction_status = f"extracao parcial: {len(rows)} preservadas; {len(rejeicoes)} rejeitadas por ancora/dependencia; revisar"
    return rows


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
    rows, documentos_sem_texto = [], []
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
        rows.extend(extrair_documento(ctx.session, doc, manifest=manifest, on_response=on_response))
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
    return {**preview, "manifest": manifest, "documentos_sem_texto": documentos_sem_texto,
        "pendencias_dominio": ["PENDENTE-ISIS: suficiência da Receita para o gate de falecimento"]
            if preview["qualificacao_cartoraria"]["falecimentos_declarados"] else [],
        "requires_review": bool(rows)}
