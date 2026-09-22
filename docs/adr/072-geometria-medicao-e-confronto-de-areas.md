# ADR-072 — Geometria: arquivo, feição, medição e confronto de áreas

- **Data:** 21/09/2026
- **Estado:** proposta em implementação (Incremento 3, branch `feat/inc3-geometria`), sem merge.
- **Autoridades:** [Plano Diretor v1.1 §4.5 e Incremento 3](../arquitetura/PLANO_DIRETOR_REGENTE_v1.1.md#45-serviço-geoespacial),
  [Arquitetura de Dados §3.6](../arquitetura/ARQUITETURA_DADOS_RAG_REGENTE_v1.md#36-geometria),
  [Mergulho §5.5 (ruptura 5)](../arquitetura/MERGULHO_ESTRUTURAL_REGENTE_2026-09-17.md#55-geometria-percurso-mínimo-obrigatório-do-mvp),
  [ADR-070 §9](070-modelo-de-dados-alvo.md#9-geometria-arquivo-feição-medição) (forma), que este ADR
  emenda no método.
- **Base medida:** main `baf7f64`; dev `amigao_db` @ `127.0.0.1:15432`, alembic `071es004`,
  PostGIS 3.3.4 / PROJ 7.2.1; produção lida só pelo `supabase-prod-ro`.

## Contexto (medido em 21/09)

1. `Property.geom` (GEOMETRY, SRID 4674) existe e **nunca é gravada**; nenhuma função `ST_*` é
   chamada em `app/`. `geo_files.py` só detecta extensão/MIME e tira o arquivo do OCR com a
   mensagem "processamento de geometria em breve".
2. Produção: **um** arquivo geoespacial em todo o banco — documento 560, `MEDIDA_POLIGONO.kmz`,
   832 bytes, caso #25 (Jobson), `ocr_status=not_required`, **sem `checksum_sha256`**. Os casos
   #22 e #23 não têm arquivo geoespacial. `properties.geom` preenchida: 0.
3. As áreas textuais já existem como **observações ancoradas** do Incremento 2
   (`evidence_versions`, `kind=observacao`), com literal e fragmento — mas o predicado é livre
   (`area_total`, `area_do_imovel`, `car_area_ha`, `area_total_ccir`…) e o valor normalizado
   vem do LLM (às vezes string, às vezes dict).
4. O comparador atual (`property_audit.compare_areas`) usa **o maior valor** como denominador e
   1% como limite do grau "informativo". A Ísis usa a **área documental**.
5. `StorageService.download_bytes` devolve `b""` também para `NoSuchBucket` (#228): bucket
   inexistente se confundia com arquivo ausente.

## Decisão

### 1. Nenhum número de área vem de LLM

Área calculada sai do PostGIS; área declarada sai de **parser determinístico sobre o literal
ancorado** da observação (`parse_area_ha`, a porta única). O `normalized` do LLM só desempata
quando o literal tem mais de um número e o valor proposto é exatamente um deles; fora disso a
medição declarada nasce `nao_determinado`, com motivo, e não entra no confronto.

### 2. Ingestão: `arquivo_geo`, uma linha por leitura, append-only

`arquivo_geo (tenant, caso, documento, numero, sha256 dos bytes, formato, membro lido,
inventário do pacote, crs_origem, estado ∈ lido|falha, falha {codigo, detalhe},
metodo_versao, lido_em)`. Reler o mesmo arquivo com o mesmo método devolve a leitura existente;
método novo gera nova linha. **Emenda ao ADR-070 §9:** `arquivo_geo` referencia o documento e o
hash dos bytes, não `documento_versao`. `documento_versao.texto` é a leitura textual projetada
em `extracted_text`, que os agentes consomem; o XML de um KML ali seria exatamente "enviar bytes
para o LLM adivinhar". O hash dos bytes cumpre o papel de versão.

- **Formatos desta entrega:** KMZ e KML. Shapefile, GeoJSON e GPX continuam detectados e viram
  **falha visível** `formato_nao_suportado` — nunca "armazenado, em breve".
- **Limites:** arquivo ≤ 20 MB; soma descompactada ≤ 50 MB; razão de compressão ≤ 100; ≤ 500
  membros. KMZ lê `doc.kml` na raiz ou o único `.kml`; mais de um sem `doc.kml` = `kml_ambiguo`.
- **XML seguro:** `lxml` com `resolve_entities=False`, `no_network=True`, `huge_tree=False`.
- **Códigos de falha:** `arquivo_ausente`, `storage_indisponivel`, `zip_invalido`,
  `limite_excedido`, `kml_ausente`, `kml_ambiguo`, `kml_invalido`, `sem_feicao`,
  `coordenada_invalida`, `formato_nao_suportado`. Falha é linha gravada e tela, não log.
- **#228:** `NoSuchBucket` deixa de virar arquivo ausente; levanta `StorageDownloadError`
  (vira `storage_indisponivel`).

### 3. Feições: `feicao`, append-only

Cada `Placemark` com geometria vira feição com `identificador_interno` (caminho
Document/Folder/Placemark por índice + `id`/`name` literais), `tipo` ∈
`poligono|multipoligono|linha|ponto`, `geom_original` (SRID 4326) e `geom` (SRID 4674),
`valida` e `motivo_invalidade` (`ST_IsValidReason`). Anéis internos e multipolígonos são
preservados; feições distintas **não são unidas**. Altitude é descartada e declarada.

**CRS:** KML 2.2 (OGC) define lon/lat WGS84; `crs_origem = EPSG:4326 (por especificação
KML 2.2)`. A transformação 4326→4674 é registrada; no PROJ do dev e da produção o 4674 tem
`towgs84=0,0,0,0,0,0,0` (identidade de coordenadas). Coordenada fora de lon ±180 / lat ±90 =
`coordenada_invalida`. Geometria inválida é gravada com `valida=false` e **não é medida**;
correção (`ST_MakeValid`) seria derivação registrada por decisão humana — fora desta entrega.

### 4. Área: geodésica no elipsoide

`ST_Area(geom::geography, true)` — área geodésica sobre o elipsoide GRS80 do SIRGAS 2000, em m²,
dividida por 10.000. Registra `metodo = postgis_st_area_geography_spheroid`,
`metodo_versao = 072.1`, `crs_calculo = EPSG:4674 (geografia, elipsoide GRS80)` e a versão do
PostGIS que calculou. Valor gravado com precisão total; tela mostra 4 casas.

### 5. Medição: `medicao`, append-only, uma linha por fonte

`medicao (tenant, caso, grandeza=area, objeto=imovel_total, origem_tipo, valor_ha nullable,
estado ∈ determinado|nao_determinado, motivo, metodo, metodo_versao, crs_calculo, documento,
feicao XOR observação, literal)`. Arco exclusivo por CHECK: `feicao_calculada` exige feição;
`declaracao_textual` e `registro` exigem a observação.

| origem_tipo | Fonte | Exemplo |
|---|---|---|
| `feicao_calculada` | feição do KMZ/KML | 2,72… ha de `MEDIDA_POLIGONO.kmz` |
| `registro` | observação em matrícula/escritura | "Área total: 2,6893." |
| `declaracao_textual` | observação em CAR/CCIR/ITR/contrato | "Área Total (ha) do Imóvel Rural: 2.180,8267" |

**Nenhuma medição sobrescreve outra.** "Área do texto do CAR", "área calculada do KMZ" e "área
registral" são linhas diferentes mesmo quando coincidem. `Property.area_grafica_ha` e
`total_area_ha` **não** são escritas pela geometria (a gráfica do CAR é outra fonte — #219).

**Objeto.** Observação só vira medição de `imovel_total` quando o predicado tem `area` e nenhum
marcador de subárea (arrendada, reserva/RL, APP, preservação, consolidada, remanescente,
vegetação, uso, servidão, hipoteca/garantia, lavoura, pastagem, benfeitoria, construída,
desmatada, embargada). Subáreas ficam fora do confronto, não viram "imóvel".

### 6. `Property.geom` é projeção de uma feição escolhida

`projecao_geometria (tenant, imóvel, caso, feição, regra|autor, motivo, criada_em)`, append-only;
`Property.geom` = geometria da última projeção. **Automática só** quando a leitura tem
exatamente uma feição poligonal válida e o imóvel ainda não tem projeção (`regra =
feicao_poligonal_unica`). Mais de uma feição poligonal, ou imóvel já projetado: escolha do
consultor por endpoint, com motivo obrigatório.

### 7. Confronto pelo auditor determinístico

`property_audit.confrontar_areas` (pura) compara **cada medição calculada com cada medição
declarada/registral determinada** do mesmo objeto e publica: os dois valores com suas fontes,
delta absoluto (ha e m²), **percentual sobre denominador declarado**, o percentual sobre o maior
(a convenção antiga, para que as duas fiquem identificadas), a tolerância e sua origem, o
resultado (`dentro_da_tolerancia|divergente|nao_calculavel`) e o grau da régua existente.

- **Denominador:** `referencia_documental` — o valor da medição declarada/registral (convenção
  da Ísis). Parâmetro, não constante espalhada.
- **Tolerância:** `settings.AUDITOR_AREA_TOLERANCIA_PCT`, **valor provisório 1,0%** — o limite
  "informativo" da régua Onda C, validada pela sócia para diferenças entre documentos.
  **Não é a resposta da Q-ISIS-04**: cada avaliação grava `tolerancia_origem =
  provisoria_regua_onda_c_pendente_q_isis_04`. Quando a Ísis fixar, muda o parâmetro e a origem;
  avaliações antigas continuam com o valor que usaram.
- **Persistência:** cada execução grava `confronto_area` append-only com `execucao` (uuid).
  Reexecutar gera **nova avaliação**; nunca atualiza a anterior, nem toca decisão humana.
- **Sem geometria:** estado derivado `nao_verificado` na leitura (não é linha, ADR-020).
- **Sobreposição/overlay:** nenhuma camada carregada ⇒ a tela diz **"não verificado"**, jamais
  "sem sobreposição". Overlays ficam para a próxima entrega deste incremento.

### 8. Onde roda

Upload (documentos e intake) e o guard do worker enfileiram `processar_geometria(doc)`; o
consultor tem "Ler geometria" na tela para arquivos já guardados — que é o caso do único KMZ de
produção, guardado sem abrir desde 13/09. O LLM não participa.

## Alternativas descartadas

| Alternativa | Por que não |
|---|---|
| `ST_Area(geometry)` em 4674 | Graus², não hectare (Plano §4.5) |
| Projetar em UTM e medir planar | Zona escolhida por centróide erra em imóvel na divisa de fuso; geodésica independe de zona |
| shapely/pyproj/fastkml no app | Três dependências novas para o que PostGIS e `lxml` (já na imagem) fazem |
| `arquivo_geo` 1:1 com `documento_versao` (ADR-070 §9 literal) | Projetaria XML em `extracted_text`, lido pelos agentes |
| Gravar a área do KMZ em `area_grafica_ha` | Sobrescreveria a área gráfica do CAR — outra fonte (#219) |
| Denominador = maior valor | Convenção não declarada; a Ísis usa a documental. Continua publicado como informativo |
| Usar `normalized` do LLM como valor declarado | Regra de ouro: LLM nunca calcula nem transcreve número sem lastro |

## Consequências

- Cinco tabelas novas append-only (trigger `rejeitar_mutacao_evidencia`), FKs compostas com
  `tenant_id`. `Property.geom` passa a ter escritor único (projeção).
- O KMZ de Jobson só é provado quando os bytes estiverem em dev: produção não é lida fora do
  `supabase-prod-ro`, e o banco não guarda o arquivo.
- Tolerância e denominador ficam trocáveis sem migration; o histórico mostra qual valeu.

## Pendente com a Ísis

- **Q-ISIS-04:** tolerância de reprodução da área do KMZ e se o limite de confronto entre fontes
  é o mesmo número. Até lá, 1,0% provisório e declarado em cada avaliação.
