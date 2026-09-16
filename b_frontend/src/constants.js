export const STATUS_LABELS = {
  ACCEPTED: 'Aceito automaticamente',
  REVIEW_REQUIRED: 'Revisão necessária',
  PENDING_INFORMATION: 'Informação pendente',
  FAILED: 'Falhou',
}

export const EVENT_TYPE_LABELS = {
  DIVIDEND: 'Dividendos',
  JCP: 'Juros sobre capital próprio',
  BONUS_SHARES: 'Bonificação em ações',
  STOCK_SPLIT: 'Desdobramento',
  REVERSE_SPLIT: 'Grupamento',
  OTHER: 'Outro evento',
  UNKNOWN: 'Evento não identificado',
}

export const FIELD_STATUS_LABELS = {
  EXTRACTED: 'Extraído',
  REFERENCE_ENRICHED: 'Enriquecido',
  DERIVED: 'Derivado',
  NOT_DISCLOSED: 'Não divulgado',
  NOT_APPLICABLE: 'Não aplicável',
  AMBIGUOUS: 'Ambíguo',
  CONFLICT: 'Conflito',
  UNREADABLE: 'Ilegível',
  UNKNOWN: 'Desconhecido',
}

export const DATE_LABELS = {
  approval_date: 'Aprovação',
  record_date: 'Data com',
  ex_date: 'Data ex',
  payment_date: 'Pagamento',
  credit_date: 'Crédito',
  fraction_period_start: 'Início de frações',
  fraction_period_end: 'Fim de frações',
}

export const FINANCIAL_LABELS = {
  gross_amount_per_share: 'Valor bruto por ação',
  net_amount_per_share: 'Valor líquido por ação',
  tax_rate_percent: 'Alíquota',
  tax_treatment: 'Tratamento tributário',
  currency: 'Moeda',
  ratio: 'Proporção',
  attributed_cost_per_share: 'Custo atribuído por ação',
}

export const EXTRACTION_STRATEGY_LABELS = {
  PYTHON: 'Leitura automática local',
  BASIC_LLM: 'Modelo de IA básico',
  STRONG_LLM: 'Modelo de IA avançado',
}

export const EXTRACTION_OUTCOME_LABELS = {
  SUFFICIENT: 'Suficiente',
  INSUFFICIENT: 'Insuficiente',
  ERROR: 'Erro',
}

export const ORIGIN_LABELS = {
  DOCUMENT: 'Documento',
  REFERENCE: 'Base de referência',
  DERIVED: 'Regra determinística',
  UNKNOWN: 'Origem desconhecida',
}

export const EXTRACTION_METHOD_LABELS = {
  NATIVE_TEXT: 'Texto nativo',
  OCR: 'OCR',
}

export const CONFIDENCE_LABELS = {
  HIGH: 'Alta',
  MEDIUM: 'Média',
  LOW: 'Baixa',
}

export const MATCH_FIELD_LABELS = {
  issuer: 'emissor',
  cnpj: 'CNPJ',
  isin: 'ISIN',
  ticker: 'código de negociação',
  share_class: 'classe do ativo',
}

export const VALIDATION_STATUS_LABELS = {
  PASS: 'Aprovada',
  WARN: 'Atenção',
  FAIL: 'Reprovada',
  NOT_APPLICABLE: 'Não se aplica',
  NOT_EVALUATED: 'Não avaliada',
}

export const VALIDATION_RULE_LABELS = {
  REF_NO_MATCH: 'Ativo não encontrado na base oficial',
  REF_STRONG_IDENTIFIER_CONFLICT: 'CNPJ e ISIN apontam para ativos diferentes',
  REF_ISSUER_MATCH: 'Emissor confere com a base oficial',
  REF_ISSUER_CONFLICT: 'Emissor diverge da base oficial',
  REF_ISIN_MATCH: 'ISIN confere com a base oficial',
  REF_ISIN_CONFLICT: 'ISIN diverge da base oficial',
  REF_CNPJ_MATCH: 'CNPJ confere com a base oficial',
  REF_CNPJ_CONFLICT: 'CNPJ diverge da base oficial',
  REF_TICKER_MATCH: 'Código de negociação confere com a base oficial',
  REF_TICKER_CONFLICT: 'Código de negociação diverge da base oficial',
  REF_SHARE_CLASS_MATCH: 'Classe do ativo confere com a base oficial',
  REF_SHARE_CLASS_CONFLICT: 'Classe do ativo diverge da base oficial',
  REF_ASSET_INACTIVE: 'Ativo consta como inativo',
  DATE_APPROVAL_AFTER_RECORD: 'Aprovação ocorre até a data com',
  DATE_RECORD_NOT_BEFORE_EX: 'Data com ocorre antes da data ex',
  DATE_PAYMENT_BEFORE_RECORD: 'Pagamento não antecede a data com',
  DATE_PAYMENT_NOT_DISCLOSED: 'Data de pagamento ainda não foi divulgada',
  FIN_GROSS_NET_TAX_CONSISTENT: 'Valores bruto, líquido e imposto são coerentes',
  FIN_GROSS_NET_TAX_MISMATCH: 'Valores bruto, líquido e imposto são incompatíveis',
  FIN_TAX_DEPENDS_ON_BENEFICIARY: 'Tributação depende do beneficiário',
  FIN_UNIVERSAL_NET_NOT_APPLICABLE: 'Valor líquido único não se aplica',
  FIN_CURRENCY_MISSING: 'Moeda não identificada',
  FIN_RATIO_VALID: 'Proporção válida',
  FIN_RATIO_INVALID: 'Proporção inválida',
  EVENT_CLASSIFICATION_SUPPORTED: 'Tipo de evento confirmado',
  EVENT_CLASSIFICATION_CONFLICT: 'Há conflito na classificação do evento',
  EVENT_REQUIRED_FIELD_MISSING: 'Falta campo obrigatório para o evento',
  EVENT_UNKNOWN: 'Tipo de evento não identificado',
}

export const REASON_LABELS = {
  EXTRACTION_CASCADE_EXHAUSTED: 'As tentativas automáticas não resolveram todos os campos críticos.',
  PAYMENT_DATE_NOT_DISCLOSED: 'A data de pagamento ainda não foi divulgada pelo emissor.',
  REFERENCE_NOT_FOUND: 'O ativo não foi confirmado na base oficial.',
  REFERENCE_IDENTIFIER_CONFLICT: 'Os identificadores extraídos divergem da base oficial.',
  DATE_SEQUENCE_INCONSISTENT: 'A sequência de datas apresenta inconsistência.',
  FINANCIAL_VALUES_INCONSISTENT: 'Os valores financeiros não são matematicamente coerentes.',
  EVENT_CLASSIFICATION_AMBIGUOUS: 'Não foi possível identificar o tipo de evento com segurança.',
  TITLE_BODY_CLASSIFICATION_CONFLICT: 'O título e o conteúdo do aviso indicam eventos diferentes.',
  CRITICAL_FIELD_LOW_CONFIDENCE: 'Um campo crítico apresenta confiança baixa.',
  DOCUMENT_PARTIALLY_UNREADABLE: 'Parte do documento não pôde ser lida com segurança.',
  PDF_CORRUPT: 'O PDF está corrompido ou não pôde ser aberto.',
  OCR_FAILED: 'A leitura das páginas digitalizadas falhou.',
  LLM_PROVIDER_UNAVAILABLE: 'O serviço de inteligência artificial está indisponível.',
  LLM_STRUCTURED_OUTPUT_INVALID: 'A resposta da inteligência artificial não respeitou o formato esperado.',
  OUTPUT_WRITE_FAILED: 'Não foi possível salvar o resultado.',
  PROCESSING_FAILED: 'O processamento do documento falhou.',
}

export const TAX_TREATMENT_LABELS = {
  NOT_APPLICABLE: 'Não se aplica',
  TAX_EXEMPT: 'Isento',
  TAX_RULE_UNIFORM: 'Tributação uniforme',
  TAX_DEPENDS_ON_BENEFICIARY: 'Depende do beneficiário',
  UNKNOWN: 'Não identificado',
}

export const FIELD_HELP = {
  'Tipo de evento': 'Natureza econômica identificada no aviso.',
  Emissor: 'Companhia responsável pelo evento corporativo.',
  CNPJ: 'Identificador fiscal usado para confirmar o emissor.',
  ISIN: 'Código internacional que identifica o ativo.',
  'Código de negociação': 'Código usado para negociar o ativo na bolsa.',
  'Classe do ativo': 'Tipo ou classe da ação informada no aviso.',
  'Segmento de listagem': 'Segmento de governança obtido na base oficial.',
  'Status do ativo': 'Situação atual do ativo na base oficial.',
  Aprovação: 'Data em que o evento foi formalmente aprovado.',
  'Data com': 'Último dia em que o investidor mantém direito ao evento.',
  'Data ex': 'Primeiro dia de negociação sem direito ao evento.',
  Pagamento: 'Data prevista para pagamento do benefício.',
  Crédito: 'Data de crédito do ativo ou valor na posição.',
  'Início de frações': 'Início do período de tratamento das frações.',
  'Fim de frações': 'Fim do período de tratamento das frações.',
  'Valor bruto por ação': 'Valor antes da retenção de impostos.',
  'Valor líquido por ação': 'Valor após a retenção de impostos.',
  Alíquota: 'Percentual de imposto aplicado ao evento.',
  'Tratamento tributário': 'Regra tributária identificada para o pagamento.',
  Moeda: 'Moeda em que os valores foram divulgados.',
  Proporção: 'Relação entre ações novas ou resultantes e ações existentes.',
  'Custo atribuído por ação': 'Custo fiscal atribuído a cada nova ação.',
}

export const FIELD_PATH_LABELS = {
  'corporate_action.event_type': 'Tipo de evento',
  'corporate_action.dates.approval_date': 'Data de aprovação',
  'corporate_action.dates.record_date': 'Data com',
  'corporate_action.dates.ex_date': 'Data ex',
  'corporate_action.dates.payment_date': 'Data de pagamento',
  'corporate_action.dates.credit_date': 'Data de crédito',
  'corporate_action.financials.gross_amount_per_share': 'Valor bruto por ação',
  'corporate_action.financials.net_amount_per_share': 'Valor líquido por ação',
  'corporate_action.financials.tax_rate_percent': 'Alíquota',
  'corporate_action.financials.currency': 'Moeda',
  'corporate_action.financials.ratio': 'Proporção',
  'issuer.name': 'Emissor',
  'issuer.cnpj': 'CNPJ',
  'security.isin': 'ISIN',
  'security.ticker': 'Código de negociação',
  'security.share_class': 'Classe do ativo',
}
