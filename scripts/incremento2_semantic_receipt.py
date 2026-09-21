"""Read dev evidence; emit counts/booleans only, never source text or raw LLM output.

Usage: python scripts/incremento2_semantic_receipt.py <tenant_id>
Superseded observations (#258) are counted apart and never enter the checks.
"""
import hashlib
import json
import re
import sys
from collections import Counter

from incremento2_dev_gate import SessionLocal

from app.models.ai_job import AIJob
from app.models.client import Client
from app.models.document import Document
from app.models.entrada_semantica import Fragmento
from app.models.evidence import EvidenceInvalidation, EvidenceReview, EvidenceVersion
from app.models.extracted_field_staging import ExtractedFieldStaging
from app.models.process import Process


def receipt(tenant_id=4):
    with SessionLocal() as db:
        docs = db.query(Document).filter_by(tenant_id=tenant_id).all()
        origins = {d.id: int(d.storage_key.rsplit('/', 1)[1]) for d in docs}
        latest = {}
        for row in db.query(EvidenceVersion).filter_by(tenant_id=tenant_id).order_by(EvidenceVersion.id):
            latest[row.object_id] = row
        superseded = {i.evidence_id for i in db.query(EvidenceInvalidation).filter_by(tenant_id=tenant_id)
                      if 'superada_por' in (i.reason or {})}
        all_obs = [r for r in latest.values() if r.kind == 'observacao']
        obs = [r for r in all_obs if r.id not in superseded]
        result = {'tenant': tenant_id, 'documents': [], 'jobs': [], 'checks': {}}
        for doc in docs:
            rows = [r for r in obs if r.source_document_id == doc.id]
            report = latest.get(f'extracao:rejeicoes:{doc.id}')
            normalized = report.content['attributes']['normalized'] if report else {}
            failures = normalized.get('rejeicoes', [])
            fields = normalized.get('campos_sem_suporte', [])
            anchored = 0
            for row in rows:
                attrs = row.content['attributes']
                frag = db.get(Fragmento, attrs.get('fragmento_id')) if attrs.get('fragmento_id') else None
                anchored += bool(frag and doc.extracted_text[frag.inicio:frag.fim] == attrs['literal'])
            result['documents'].append({'origin': origins[doc.id], 'dev': doc.id,
                'chars': len(doc.extracted_text), 'bytes': len(doc.extracted_text.encode()),
                'sha256': hashlib.sha256(doc.extracted_text.encode()).hexdigest(),
                'observations': len(rows), 'valid_offsets': anchored,
                'superseded': sum(1 for r in all_obs if r.source_document_id == doc.id and r.id in superseded),
                'types': dict(Counter((r.source_record or {}).get('tipo_entrada') for r in rows)),
                'rejected': len(failures), 'reasons': dict(Counter(r['motivo'] for r in failures)),
                'unsupported_fields': dict(Counter(re.sub(r'\[\d+\]$', '', f['campo']) for f in fields)),
                'status': doc.extraction_status})
        for job in db.query(AIJob).filter_by(tenant_id=tenant_id, agent_name='extrator').order_by(AIJob.id):
            calls = json.loads(job.raw_output or '[]')
            seconds = (job.finished_at - job.started_at).total_seconds() if job.finished_at and job.started_at else None
            result['jobs'].append({'id': job.id, 'status': str(job.status), 'model': job.model_used,
                'tokens_in': job.tokens_in, 'tokens_out': job.tokens_out, 'cost_usd': job.cost_usd,
                'seconds': seconds, 'calls': [c['label'] for c in calls],
                'error_type': (job.error or '').split('input_value=')[0][:180]})

        def items(origin, kind):
            return [r.content['attributes']['normalized'] for r in obs
                    if origins.get(r.source_document_id) == origin and (r.source_record or {}).get('tipo_entrada') == kind]
        matrices = {}
        for origin in (547, 548, 549, 550):
            matrices[origin] = sorted({(re.sub(r'\D', '', a.get('matricula') or ''), a.get('cns') or a.get('serventia'))
                                      for a in items(origin, 'ato_registral') if a.get('matricula') and a.get('serventia')})
        result['matricula_identities'] = matrices
        clients = {p.id: db.get(Client, p.client_id) for p in db.query(Process).filter_by(tenant_id=tenant_id)}
        result['checks']['pj_cnpj_preserved'] = any(getattr(c.client_type, 'value', c.client_type) == 'pj'
            and re.sub(r'\D', '', c.cpf_cnpj or '') == '29091958000117' for c in clients.values())
        deed_parties = {p['chave']: p for p in items(559, 'parte')}
        sellers = [deed_parties[p['parte_chave']]['nome'] for p in items(559, 'participacao')
                   if p['papel'] == 'transmitente' and p['parte_chave'] in deed_parties]
        result['checks']['ivair_elda_transmitentes'] = all(any(n in name.upper() for name in sellers) for n in ('IVAIR', 'ELDA'))
        result['checks']['sellers_not_clients'] = not any(any(n in c.full_name.upper() for n in ('IVAIR', 'ELDA')) for c in clients.values())
        deaths = items(557, 'falecimento_declarado')
        result['checks']['receita_death_observation'] = bool(deaths)
        result['checks']['receita_death_year'] = any(d.get('ano') for d in deaths)
        result['checks']['receita_consultation_date'] = any(d.get('data_consulta') for d in deaths)
        result['checks']['estate_from_contract'] = any(p['natureza'] == 'espolio' and p.get('falecido_chave') for p in items(558, 'parte'))
        result['checks']['estate_without_own_identifier'] = all(not p.get('identificador') for p in items(558, 'parte')
                                                                if p['natureza'] == 'espolio')
        result['checks']['contract_extracted'] = bool(items(558, 'contrato'))
        result['checks']['inventory_from_contract'] = any(c.get('referencia_processo_judicial') for c in items(558, 'contrato'))
        result['checks']['inventariante_declared'] = any(p['papel'] == 'inventariante' and p.get('representado_chave')
            and p['estado_confirmacao'] == 'declarado' for p in items(558, 'participacao'))
        result['checks']['nothing_confirmed'] = all(p.get('estado_confirmacao') != 'confirmado'
                                                    for origin in (558, 559) for p in items(origin, 'participacao'))
        result['checks']['deed_not_certidao'] = all((r.source_record or {}).get('especie_documental') == 'escritura_publica'
            for r in obs if origins.get(r.source_document_id) == 559) and bool(items(559, 'parte'))
        result['staging_references'] = db.query(ExtractedFieldStaging).filter_by(tenant_id=tenant_id).filter(
            ExtractedFieldStaging.observacao_ref.isnot(None)).count()
        result['staging_to_superseded'] = db.query(ExtractedFieldStaging).filter(
            ExtractedFieldStaging.tenant_id == tenant_id, ExtractedFieldStaging.observacao_ref.in_(superseded or {0})).count()
        result['knowledge_states'] = dict(Counter(r.content['knowledge']['state'] for r in obs))
        result['human_reviews'] = db.query(EvidenceReview).filter_by(tenant_id=tenant_id).count()
        return result


if __name__ == '__main__':
    print(json.dumps(receipt(int(sys.argv[1]) if len(sys.argv) > 1 else 4), ensure_ascii=True))
