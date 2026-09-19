"""ADR-070 roteiro passo 4: pessoas, atos e projeção de observação.

Expansão apenas; nenhuma pessoa, papel ou serventia inferida do legado.
"""
from alembic import op

revision = "071es004"
down_revision = "071es003"
branch_labels = None
depends_on = None

TABLES = {
    "classificacao_documento": """documento_id integer NOT NULL, versao integer NOT NULL CHECK(versao>0),
      tipo_original text, tipo_proposto text NOT NULL, tipo_revisado text,
      responsavel_id integer REFERENCES users(id), motivo text NOT NULL CHECK(length(trim(motivo))>0),
      created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(documento_id,versao),
      CHECK(tipo_revisado IS NULL OR responsavel_id IS NOT NULL),
      FOREIGN KEY(tenant_id,documento_id) REFERENCES documents(tenant_id,id)""",
    "pessoa": """nome text NOT NULL, natureza text NOT NULL CHECK(natureza IN ('pf','pj','indeterminada')),
      aliases jsonb NOT NULL DEFAULT '[]', origem_observacao_id integer NOT NULL UNIQUE,
      estado text CHECK(estado IS NULL OR estado='falecimento_declarado'), estado_fundamento_id integer,
      CHECK((estado IS NULL)=(estado_fundamento_id IS NULL)),
      CHECK(estado IS NULL OR natureza='pf'),
      FOREIGN KEY(tenant_id,estado_fundamento_id) REFERENCES evidence_versions(tenant_id,id),
      FOREIGN KEY(tenant_id,origem_observacao_id) REFERENCES evidence_versions(tenant_id,id)""",
    "pessoa_identificador": """pessoa_id integer NOT NULL, tipo text NOT NULL, valor text NOT NULL,
      fundamento_id integer NOT NULL, estado_confirmacao text NOT NULL,
      FOREIGN KEY(tenant_id,fundamento_id) REFERENCES evidence_versions(tenant_id,id),
      FOREIGN KEY(tenant_id,pessoa_id) REFERENCES pessoa(tenant_id,id)""",
    "espolio": """falecido_id integer NOT NULL, inventario text,
      fundamento_id integer NOT NULL UNIQUE,
      FOREIGN KEY(tenant_id,fundamento_id) REFERENCES evidence_versions(tenant_id,id),
      FOREIGN KEY(tenant_id,falecido_id) REFERENCES pessoa(tenant_id,id)""",
    "serventia": """nome text NOT NULL, cns text, motivo_cns_ausente text, localidade text,
      especialidade text NOT NULL, documento_origem_id integer NOT NULL,
      FOREIGN KEY(tenant_id,documento_origem_id) REFERENCES documents(tenant_id,id),
      CHECK(cns IS NOT NULL OR (motivo_cns_ausente IS NOT NULL AND length(trim(motivo_cns_ausente))>0))""",
    "ato_registral": """process_id integer NOT NULL, serventia_id integer NOT NULL,
      matricula_numero text NOT NULL, rotulo text NOT NULL, especie text NOT NULL,
      natureza text NOT NULL, data_ato date, precisao_data text NOT NULL, ordem_fonte integer NOT NULL,
      UNIQUE(tenant_id,process_id,id), UNIQUE(tenant_id,process_id,serventia_id,matricula_numero,rotulo),
      FOREIGN KEY(tenant_id,serventia_id) REFERENCES serventia(tenant_id,id)""",
    "participacao": """process_id integer NOT NULL, pessoa_id integer, espolio_id integer,
      ato_id integer, documento_id integer, caso_id integer,
      papel text NOT NULL CHECK(papel IN ('adquirente','transmitente','titular_direito','representante',
      'inventariante','herdeiro','meeiro','credor','devedor','confrontante','declarante','indeterminado')),
      vocabulario_versao text NOT NULL, estado_confirmacao text NOT NULL CHECK(estado_confirmacao IN ('declarado','confirmado')),
      fundamento_id integer NOT NULL, representado_pessoa_id integer, representado_espolio_id integer,
      alcance text, inicio date, fim date, fracao numeric(18,12) CHECK(fracao>0 AND fracao<=1),
      CHECK(num_nonnulls(pessoa_id,espolio_id)=1), CHECK(num_nonnulls(ato_id,documento_id,caso_id)=1),
      CHECK(num_nonnulls(representado_pessoa_id,representado_espolio_id)<=1), CHECK(fim IS NULL OR inicio IS NULL OR fim>=inicio),
      CHECK(estado_confirmacao='declarado' OR papel NOT IN ('inventariante','representante')
         OR (documento_id IS NOT NULL AND alcance IS NOT NULL AND inicio IS NOT NULL
         AND fim IS NOT NULL AND num_nonnulls(representado_pessoa_id,representado_espolio_id)=1)),
      FOREIGN KEY(tenant_id,pessoa_id) REFERENCES pessoa(tenant_id,id),
      FOREIGN KEY(tenant_id,espolio_id) REFERENCES espolio(tenant_id,id),
      FOREIGN KEY(tenant_id,representado_pessoa_id) REFERENCES pessoa(tenant_id,id),
      FOREIGN KEY(tenant_id,representado_espolio_id) REFERENCES espolio(tenant_id,id),
      FOREIGN KEY(tenant_id,documento_id) REFERENCES documents(tenant_id,id),
      FOREIGN KEY(tenant_id,process_id,ato_id) REFERENCES ato_registral(tenant_id,process_id,id),
      FOREIGN KEY(tenant_id,process_id,fundamento_id) REFERENCES evidence_versions(tenant_id,process_id,id)""",
    "relacao_ato": """process_id integer NOT NULL, origem_id integer NOT NULL, destino_id integer NOT NULL,
      tipo text NOT NULL CHECK(tipo IN ('baixa','aditivo','retificacao','cancelamento')), fundamento_id integer NOT NULL,
      CHECK(origem_id<>destino_id),
      FOREIGN KEY(tenant_id,process_id,origem_id) REFERENCES ato_registral(tenant_id,process_id,id),
      FOREIGN KEY(tenant_id,process_id,destino_id) REFERENCES ato_registral(tenant_id,process_id,id),
      FOREIGN KEY(tenant_id,process_id,fundamento_id) REFERENCES evidence_versions(tenant_id,process_id,id)""",
}


def upgrade():
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.execute("ALTER TABLE evidence_versions ADD CONSTRAINT uq_ev_tenant_id UNIQUE(tenant_id,id)")
    for table, columns in TABLES.items():
        op.execute(f"CREATE TABLE {table}(id serial PRIMARY KEY, tenant_id integer NOT NULL REFERENCES tenants(id), "
                   f"{columns}, UNIQUE(tenant_id,id))")
    for table in ("classificacao_documento", "pessoa_identificador", "participacao", "relacao_ato"):
        op.execute(f"CREATE TRIGGER {table}_imutavel BEFORE UPDATE OR DELETE ON {table} "
                   "FOR EACH ROW EXECUTE FUNCTION public.rejeitar_mutacao_evidencia()")
    op.execute("ALTER TABLE clients ADD COLUMN pessoa_id integer")
    op.execute("ALTER TABLE clients ADD CONSTRAINT fk_client_pessoa FOREIGN KEY(tenant_id,pessoa_id) REFERENCES pessoa(tenant_id,id)")
    op.execute("ALTER TABLE matriculas ADD COLUMN serventia_id integer")
    op.execute("ALTER TABLE matriculas ADD CONSTRAINT fk_matricula_serventia FOREIGN KEY(tenant_id,serventia_id) REFERENCES serventia(tenant_id,id)")
    op.execute("ALTER TABLE extracted_field_staging ADD COLUMN observacao_ref integer")
    op.execute("""ALTER TABLE extracted_field_staging ADD CONSTRAINT fk_staging_observacao
      FOREIGN KEY(tenant_id,process_id,observacao_ref) REFERENCES evidence_versions(tenant_id,process_id,id)""")


def downgrade():
    op.execute("ALTER TABLE extracted_field_staging DROP COLUMN observacao_ref")
    op.execute("ALTER TABLE matriculas DROP COLUMN serventia_id")
    op.execute("ALTER TABLE clients DROP COLUMN pessoa_id")
    for table in reversed(TABLES):
        op.drop_table(table)
    op.drop_constraint("uq_ev_tenant_id", "evidence_versions")
