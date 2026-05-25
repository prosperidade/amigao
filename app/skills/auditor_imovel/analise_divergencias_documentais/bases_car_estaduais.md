# Bases de CAR por estado — anexo do auditor_imovel

Roteiro de expansão nacional. Mapa, por UF, do órgão estadual e do sistema de CAR ligado ao
SICAR. Fonte: complemento da sócia (consolidado por ela com referências oficiais). Hoje o Regente
cobre **GO + MS + MT + Federal**; este anexo é o mapa de onde buscar o CAR nos demais estados
quando a expansão chegar. **Para conferência automática, todas dependem de integração futura** —
no MVP o cliente sobe o recibo/consulta do CAR e o auditor cruza o documento.

> Bases **prioritárias hoje:** GO (SIGCAR + Portal Ambiental SEMAD), MT (SIMCAR), MS (SIRIEMA).

## Norte
| UF | Órgão | Sistema de CAR | Observação |
|---|---|---|---|
| AC | SEMA/IMAC | SICAR-Acre / CIGMA-CAR | Gestão estadual do CAR/PRA; disponibiliza base shapefile dos imóveis |
| AP | SEMA/AP | SICAR Nacional | Usa o SICAR nacional (cadastro, receptor, relatórios, análise) |
| AM | IPAAM / SEMA-AM | SICAR-AM / CAR Amazonas | Referência normativa própria, SICAR-AM e PRA estadual |
| PA | SEMAS/PA | SICAR/PA → SICAR+ / Regulariza Pará | Sistema próprio; SICAR+ anunciado em 2026 (modernização) |
| RO | SEDAM/RO | SICAR.RO / GeoPortal SEDAM | Geoportal permite busca de feições por CAR — útil p/ cruzamento espacial |
| RR | FEMARH/RR | Gestão SICAR / SIGGARR | SIGGARR = SIG e Gestão Ambiental de Roraima |
| TO | Naturatins | SICAR/TO / SIGCAR-TO | Sistema estadual anterior ao federal, com integração |

## Nordeste
| UF | Órgão | Sistema de CAR | Observação |
|---|---|---|---|
| AL | IMA/AL | SICAR/AL | CAR no SICAR nacional, gerenciado/homologado pelo IMA |
| BA | INEMA / SEMA-BA | CEFIR / SEIA | CAR implementado como CEFIR (Cadastro Estadual Florestal), ligado a licenciamento e outorga |
| CE | SEMACE | SICAR Ceará / CAR Analisado | Produto "CAR Analisado" com status atualizado |
| MA | SEMA/MA | SICAR Nacional | Inscrição pelo módulo do SICAR nacional |
| PB | SUDEMA/PB | CAR Paraíba / SICAR | Formulários e procedimentos estaduais vinculados ao SICAR |
| PE | CPRH | SICAR Pernambuco / Central do Proprietário | Central do proprietário, retificação, PRA |
| PI | SEMARH/PI | SIGA-PI / SICAR | SIGA-PI = sistema integrado de gestão ambiental e recursos hídricos |
| RN | IDEMA/RN | CAR/RN / SICAR | Procedimentos e formulários estaduais ligados ao SICAR |
| SE | ADEMA/SE | CAR/SICAR Sergipe | ADEMA é gestora estadual; analisa e atua com municípios |

## Centro-Oeste
| UF | Órgão | Sistema de CAR | Observação |
|---|---|---|---|
| DF | Brasília Ambiental / IBRAM | CAR/DF / SICAR | IBRAM direciona ao SICAR nacional + suporte e análise |
| **GO** | **SEMAD/GO** | **SIGCAR Goiás / Portal Ambiental SEMAD** | **Base prioritária. SIGCAR lançado em 2025 — sistema estadual próprio do CAR** |
| MT | SEMA/MT | SIMCAR | Sistema mato-grossense integrado ao SICAR nacional |
| MS | IMASUL | SIRIEMA / SICAR Nacional | CAR-MS feito eletronicamente pelo SIRIEMA, integrado ao nacional |

## Sudeste
| UF | Órgão | Sistema de CAR | Observação |
|---|---|---|---|
| ES | IDAF/ES | SICAR / SIMLAM-IDAF | SIMLAM como sistema de análises técnicas |
| MG | IEF / SISEMA | SICAR-MG / SISEMA | Opera no ambiente SISEMA/IEF; gestão estadual de análise |
| RJ | INEA/RJ | SICAR/RJ | Procedimentos estaduais de análise e validação no SICAR |
| SP | SEMIL/SP | SiCAR-SP | Portal próprio, Central do Proprietário, demonstrativos de análise |

## Sul
| UF | Órgão | Sistema de CAR | Observação |
|---|---|---|---|
| PR | IAT/PR | SICAR/PR / Central da Regularização | Portal próprio e lei estadual que institui o sistema |
| RS | SEMA/RS | CAR-RS / SICAR Nacional | Migrou para a plataforma federal em 2024; mantém página estadual |
| SC | IMA/SC | SICAR/SC (car.sc.gov.br) | Página própria, Central do Proprietário, módulo estadual integrado ao nacional |

---

**Leitura para o produto:** o CAR é federal na origem (SICAR) mas **gerido por sistemas estaduais
heterogêneos**. Alguns estados usam o SICAR nacional puro (AP, MA); outros têm plataforma própria
relevante (GO/SIGCAR, MT/SIMCAR, MS/SIRIEMA, BA/CEFIR, SP/SiCAR-SP, PR, RO/GeoPortal). Para o
auditor, isso significa: (1) o documento que o cliente sobe pode vir de qualquer um desses; (2) a
conferência automática (futura) exige um conector por estado; (3) a expansão nacional não é "ligar
uma API" — é mapear sistema por sistema. GO/MT/MS já cobertos; o resto é backlog priorizável por
demanda.
