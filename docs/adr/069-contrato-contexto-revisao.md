# ADR-069 — Contrato de evidência, contexto e revisão

- Data: 2026-09-17
- Estado: proposta implementada em branch; integração e aceite dependem dos gates do PR #172
- Referência de execução: [Plano Diretor v1.1, §8](../arquitetura/PLANO_DIRETOR_REGENTE_v1.1.md)
- Análise: [Mergulho estrutural](../arquitetura/MERGULHO_ESTRUTURAL_REGENTE_2026-09-17.md)
- Complementa ADR-006, ADR-007, ADR-011 e ADR-068. Não autoriza merge ou deploy.

## Decisão

`build_envelope` é o construtor do contexto autorizado por tenant, usuário ativo e
caso. UI, API, `BaseAgent.run`, worker e retomada usam a mesma execução persistida.
Metadata do cliente não determina UF, tenant, objetivo nem conclusões. UF é
normalizada, conserva origem e conflito; desconhecido não vira GO. Objetivo
classificado e tipo sugerido conservam suas origens distintas.

`EvidenceObject` representa fonte primária, observação, derivação e conclusão.
`EvidenceVersion` guarda conteúdo imutável e hash, com identidade por caso e
versão. `SourceRef` e `Afirmacao` recebem referências a essa identidade: são
projeções de compatibilidade, não outra escrita canônica. Derivações guardam
entradas e versão do método; a matriz existente produz comparação e conclusão
separadas. Isso não equivale a implementar os motores dos incrementos 2–4.

Conhecimento e execução são eixos distintos. Ausência verificada exige consulta,
escopo, identificadores, data e resposta preservada. Material não localizado exige
cobertura. Não aplicável exige premissas e justificativa. Referências são
resolvidas no mesmo caso; texto de agente não pode se declarar fonte primária.
O default legado `has_embargo=False` não entra como evidência negativa.

## Revisão e atualidade

Revisões são eventos com autor, data, motivo, revisão otimista e versões das
premissas. Correção cria versão **pendente**. Não aplicável cria versão própria e
decisão explícita. A versão anterior e todos os eventos permanecem consultáveis.
O journal de revisão participa da hash chain do tenant.

Só conclusões aprovadas/não aplicáveis, atuais e com dependências recuperáveis
entram no envelope seguinte. Rejeição não apaga documento nem observação. Nenhum
resultado bruto, resumo ou último `AIJob.completed` serve de rota paralela.
Observações propostas podem ser lidas como propostas, com estado de revisão
explícito; observações rejeitadas não entram como entradas de comparação.

Versão de premissa alterada invalida transitivamente seus dependentes, preservando
a aprovação anterior. A comparação declara os documentos participantes; verificações
de presença dependem também do inventário versionado. Não há retrocesso automático
de etapa. O consultor pode solicitar retorno à coleta ou reavaliação dos passos
desatualizados; seus resultados anteriores permanecem no histórico.

## Execução e transação

`AgentExecution` guarda snapshot, passos, dependências, cursor, revisão e chave
idempotente. Lock transacional por caso e unicidade impedem duas retomadas
concorrentes de gravarem o mesmo efeito. Gestos aguardam contenção breve de
atualização do painel por até um segundo; contenção persistente retorna conflito,
sem repetir efeito. Leituras independentes continuam; síntese
aguarda apenas suas dependências. `completed` exige todos os passos previstos e
suas revisões resolvidas. Rejeitar resolve a revisão, mas não autoriza consumir o
texto rejeitado. `stop_on_review=False` não contorna o gate.

Ao retomar, próximos passos recebem snapshot atualizado; cada job conserva o
snapshot e contexto exatos que realmente consumiu. Reavaliação de efeito
desatualizado é um gesto explícito, distinto da retomada idempotente.

Serviços fazem flush, não commit de resultados intermediários; a entrada controla
commit/rollback. Worker diferencia erro determinístico e erro de conexão.
Chamadas externas não são transacionais: queda depois de o provider atender e
antes do commit pode repetir custo em nova tentativa. Não se promete exactly-once
de cobrança do provider. Efeitos persistidos concluídos não são repetidos.

## Manifesto, skills e capacidades

AIJob registra envelope/hash, prompt-base e versão/hash, mensagens compostas,
skills/anexos com conteúdo e hash, parâmetros efetivos, provider/modelo, tentativas,
respostas brutas, término, custo disponível e erro de parse. Credenciais não entram
no manifesto. Citações normativas exigem fonte versionada recuperável; a lista
histórica de normas da skill não é uma consulta atual.

Seis nomes ativos: extrator, auditor_imovel, legislacao, diagnostico, redator e
orcamento. Atendimento, financeiro, marketing, acompanhamento e vigia ficam
congelados na UI, API, entrada de worker e beat, inclusive mensagens antigas.

Há **duas skills reais**, reconciliadas em v1.3.0: auditor e diagnóstico. Não foram
criadas skills nem métodos de domínio novos. As outras quatro responsabilidades
ativas, sem método-base declarado no catálogo, reportam capacidade insuficiente;
seus placeholders não são capacidade. Fora de GO/MS/MT ou com UF desconhecida, a
skill regional de diagnóstico é não aplicável e a falta de método geral fica
explícita. O auditor declara cobertura parcial de comparação documental, não
execução integral de todas as heurísticas da skill.

A revisão semântica removeu desconhecimento→risco alto em H1, lacuna→crítico no
consolidado, ausência→contratação, sobreposição presumida e passagem por
`chain_data`; qualificou CAR coletivo, formalização de RL e exemplos de dispensa.
Isso é compatibilização do contrato, **não homologação jurídica das normas ou
aceite de domínio da sócia**. As referências históricas continuam sujeitas à
recuperação e ao teste de aplicabilidade.

## Retenção e legado

Texto, hash disponível, identidade do storage, documento e versão usados são
copiados no registro de evidência. FKs RESTRICT impedem apagar fisicamente caso,
documento ou job ainda referenciado. Soft-delete não apaga essa prova; a rota de
consulta de versão continua autorizada pelo tenant mesmo após arquivamento.
Não se fabricam páginas, hashes ou datas que o legado não registrou. Importação
sob demanda do staging mantém ID legado e qualificação `legacy_unverified`.
Jobs antigos continuam no histórico, sem aprovação implícita e sem importação
automática de seus textos como premissas.

O objeto original no bucket deve ser retido enquanto houver referência; esta
mudança não configura lifecycle no R2 nem comprova integridade dos bytes de todos
os arquivos legados. Não há expurgo automático novo.

## Validação e limites

Contrato e percurso autenticado usam PostgreSQL real e sessões com commit. Só a
resposta do LLM é controlada. Transporte Celery eager prova o corpo do worker,
não um broker remoto. O gate de navegador usa o build real e login pela UI,
rejeição, F5, correção, nova sessão, histórico e retomada. CI executa também a
suíte completa e upgrade/downgrade das migrations.

Testes históricos de algoritmos e projeções foram apontados explicitamente ao
harness legado isolado: não são prova da execução autorizada nova. Expectativas
de consumo bruto sem revisão em ADR-011 foram substituídas por testes reais de
dependências. Fonte única não comprova confronto; expectativa antiga de
consistência com uma fonte foi substituída por atenção, conforme a triagem do #171.
Entrada manual não exige atendimento congelado nem aceita marcação por intake.

Provas usam documentos sintéticos identificados como fixtures. Não reextraem nem
homologam Jobson, ELODI ou outros originais; não afirmam cobertura jurídica,
geoespacial ou disponibilidade em produção. O PR #171 foi fechado sem merge;
o destino de seu conteúdo está na [triagem indexada](../auditoria/TRIAGEM_PR171_PLANO_V1_1.md).
