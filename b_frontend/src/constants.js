export const STATUS_LABELS = {
  ACCEPTED: 'Aceito automaticamente',
  REVIEW_REQUIRED: 'Revisão necessária',
  PENDING_INFORMATION: 'Informação pendente',
  FAILED: 'Falhou',
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
  PYTHON: 'Python determinístico',
  BASIC_LLM: 'LLM básica',
  STRONG_LLM: 'LLM forte',
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
