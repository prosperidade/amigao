/**
 * Rótulo do alerta regulatório em português de consultora.
 *
 * Antes disto a tela mostrava o `codigo_alerta` cru — `AUTO_INFRACAO_PASSIVO`,
 * `RL_MATRICULA_DIVERGENTE_RL_CAR` — em três lugares (Visão geral, Hub do
 * Imóvel, assinatura do diagnóstico) e ainda o usava como título de Ação
 * ("Resolver alerta: AUTO_INFRACAO_PASSIVO").
 *
 * O que motivou a correção agora foi o VOCABULÁRIO, não a estética (validação
 * da Isis): `AUTO_INFRACAO_PASSIVO` chama de "passivo" um ATO do órgão. Na
 * linguagem dela a ordem é a inversa e importa — o **passivo** é o fato
 * consumado (supressão irregular, APP ocupada); o auto de infração, o embargo e
 * a multa são **atos** que o passivo gerou. Tratar o auto como se fosse o
 * passivo faz o consultor procurar o problema no lugar errado: ele vai discutir
 * a peça em vez de apurar o fato que a originou.
 *
 * A mesma correção já tinha sido feita nos prompts em 30/07
 * (`app/agents/diagnostico.py`, `app/agents/legislacao.py`) — o catálogo ficou
 * de fora, e é o catálogo que aparece na tela.
 *
 * NOTA DE ARQUITETURA: `regulatory_catalog.label` já existe no banco com um
 * texto para cada código, mas a API de issues não o devolve
 * (`app/schemas/regulatory.py` não tem `label`). Este dicionário é o rótulo que
 * chega à consultora HOJE; expor o label do catálogo pela API é o conserto
 * estrutural, registrado como dívida para não mantermos duas listas para
 * sempre.
 */

const ALERTA_LABEL: Record<string, string> = {
  // ── Restrição / risco ────────────────────────────────────────────────────
  // O par que motivou esta tabela. "Auto de infração" é o ato; o passivo é o
  // que o gerou — e é ele que o caso precisa resolver.
  AUTO_INFRACAO_PASSIVO: 'Auto de infração — apurar o passivo que o originou',
  EMBARGO_NAO_INFORMADO: 'Embargo do IBAMA não informado',
  RESTRICAO_TERRITORIAL_NAO_INFORMADA:
    'Restrição territorial (UC, APA, terra indígena, quilombola) não informada',

  // ── Área ─────────────────────────────────────────────────────────────────
  AREA_MATRICULA_X_CAR: 'Área da matrícula diverge do CAR',
  AREA_MATRICULA_X_GEO: 'Área da matrícula diverge do GEO/SIGEF',
  AREA_MATRICULA_X_CCIR: 'Área da matrícula diverge do CCIR',
  AREA_MATRICULA_X_ITR: 'Área da matrícula diverge do ITR',
  AREA_CAR_X_GEO: 'Área do CAR diverge do GEO/SIGEF',
  AREA_CAR_X_CCIR: 'Área do CAR diverge do CCIR',
  AREA_CAR_X_ITR_CIB: 'Área do CAR diverge do ITR/CIB',
  AREA_SOMA_MATRICULAS_X_CAR: 'Soma das matrículas diverge da área do CAR',

  // ── GEO / INCRA ──────────────────────────────────────────────────────────
  GEO_AUSENTE: 'Matrícula sem georreferenciamento certificado pelo INCRA',
  GEO_CERTIFICADO_NAO_AVERBADO: 'GEO certificado, mas não averbado na matrícula',
  SIGEF_TITULAR_ANTIGO: 'SIGEF ainda mostra o proprietário anterior',
  SIGEF_NOME_IMOVEL_DIVERGENTE_MATRICULA: 'Nome do imóvel no SIGEF diverge da matrícula',
  SIGEF_REGISTRO_CARTORIO_NAO_CONFIRMADO: 'GEO certificado sem averbação em cartório',

  // ── CAR ──────────────────────────────────────────────────────────────────
  CAR_LOCALIZACAO_DIVERGENTE_REALIDADE: 'CAR deslocado da realidade',
  CAR_ANTERIOR_AO_GEO_REQUER_RETIFICACAO: 'CAR feito antes do GEO — requer retificação',
  CAR_MATRICULA_NAO_RASTREAVEL: 'CAR não permite rastrear a matrícula',

  // ── Geoespacial ──────────────────────────────────────────────────────────
  GEO_POLIGONO_DESLOCADO_CAR: 'Polígono do GEO deslocado do CAR',
  GEO_SOBREPOSICAO_TERCEIRO: 'Sobreposição com imóvel de terceiro',
  GEO_CONFRONTANTES_DIVERGENTES: 'Confrontantes divergem entre as fontes',
  GEO_ERRO_DATUM_FUSO_PROJECAO: 'Erro de datum, fuso ou projeção no arquivo',

  // ── Ambiental ────────────────────────────────────────────────────────────
  RL_MATRICULA_DIVERGENTE_RL_CAR: 'Reserva Legal averbada diverge da declarada no CAR',
  RL_CAR_X_REALIDADE: 'Reserva Legal declarada não aparece na imagem',
  RL_INSUFICIENTE: 'Percentual de Reserva Legal aparenta insuficiente para o bioma',
  APP_OMITIDA: 'APP omitida no CAR',
  // Aqui "passivo" está CERTO: APP ocupada é o fato consumado.
  APP_OCUPADA: 'APP ocupada — passivo a regularizar',
  AREA_CONSOLIDADA_DUVIDOSA: 'Área consolidada duvidosa',
  SUPRESSAO_SEM_AUTORIZACAO_APARENTE: 'Supressão de vegetação sem autorização aparente',
  VEGETACAO_NATIVA_SUBDECLARADA: 'Vegetação nativa subdeclarada (oportunidade de PSA/carbono)',

  // ── Fiscal / cadastral ───────────────────────────────────────────────────
  CCIR_TITULAR_DESATUALIZADO: 'CCIR com titular desatualizado',
  CCIR_EXERCICIO_ANTERIOR: 'CCIR de exercício anterior',
  ITR_CIB_DIVERGENTE: 'ITR/CIB diverge entre as fontes',
  ONUS_GARANTIA_BANCARIA: 'Ônus, hipoteca, alienação ou penhora na matrícula',

  // ── Validade documental ──────────────────────────────────────────────────
  DOCUMENTO_DESATUALIZADO_OU_VENCIDO: 'Documento desatualizado ou vencido',
  DOCUMENTO_AUSENTE: 'Documento essencial ausente',
  OUTRO_GENERICO: 'Achado sem código específico',

  // ── Licenciamento ────────────────────────────────────────────────────────
  LICENCA_OUTORGA_AUSENTE_VENCIDA: 'Licença ou outorga ausente ou vencida',
};

/**
 * Rótulo legível de um `codigo_alerta`.
 *
 * O catálogo é EVOLUTIVO por decisão de projeto (código novo entra sem
 * migration), então esta tabela sempre estará um passo atrás em algum momento.
 * Código desconhecido degrada com elegância — vira frase capitalizada em vez de
 * sumir ou aparecer em caixa alta — e nunca cancela a tela por não estar aqui.
 */
export function alertaLabel(codigo: string | null | undefined): string | null {
  if (!codigo) return null;
  const conhecido = ALERTA_LABEL[codigo];
  if (conhecido) return conhecido;
  const humanizado = codigo.replace(/_/g, ' ').trim().toLowerCase();
  if (!humanizado) return null;
  return humanizado.charAt(0).toUpperCase() + humanizado.slice(1);
}

export { ALERTA_LABEL };
