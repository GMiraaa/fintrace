export type EventType =
  | 'DIVIDEND'
  | 'JCP'
  | 'BONUS_SHARES'
  | 'STOCK_SPLIT'
  | 'REVERSE_SPLIT'
  | 'OTHER'
  | 'UNKNOWN'

export type FieldStatus =
  | 'EXTRACTED'
  | 'REFERENCE_ENRICHED'
  | 'DERIVED'
  | 'NOT_DISCLOSED'
  | 'NOT_APPLICABLE'
  | 'AMBIGUOUS'
  | 'CONFLICT'
  | 'UNREADABLE'
  | 'UNKNOWN'

export type Origin = 'DOCUMENT' | 'REFERENCE' | 'DERIVED' | 'UNKNOWN'
export type ExtractionMethod = 'NATIVE_TEXT' | 'OCR'
export type ValidationStatus = 'PASS' | 'WARN' | 'FAIL' | 'NOT_APPLICABLE' | 'NOT_EVALUATED'
export type ProcessingStatus = 'ACCEPTED' | 'REVIEW_REQUIRED' | 'PENDING_INFORMATION' | 'FAILED'
export type ExtractionStrategy = 'PYTHON' | 'BASIC_LLM' | 'STRONG_LLM'
export type ExtractionAttemptOutcome = 'SUFFICIENT' | 'INSUFFICIENT' | 'ERROR'

export type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue }

export interface SourceEvidence {
  page: number
  evidence: string
  extraction_method: ExtractionMethod
}

export interface ValidationResult {
  rule: string
  status: ValidationStatus
  message: string
  expected?: JsonValue
  observed?: JsonValue
}

export interface AuditableField<T = string> {
  value: T | null
  status: FieldStatus
  origin: Origin
  confidence: number
  agent_agreement: number | null
  sources: SourceEvidence[]
  validation: ValidationResult[]
}

export interface RatioValue {
  kind: 'NEW_PER_EXISTING' | 'RESULTING_PER_EXISTING'
  numerator: string
  denominator: string
  percentage: string | null
}

export interface SourceDocument {
  file_name: string
  sha256: string
  page_count: number
  extraction_methods: ExtractionMethod[]
}

export interface EventDates {
  approval_date: AuditableField<string>
  record_date: AuditableField<string>
  ex_date: AuditableField<string>
  payment_date: AuditableField<string>
  credit_date: AuditableField<string>
  fraction_period_start: AuditableField<string>
  fraction_period_end: AuditableField<string>
}

export interface Financials {
  gross_amount_per_share: AuditableField<string>
  net_amount_per_share: AuditableField<string>
  tax_rate_percent: AuditableField<string>
  tax_treatment: AuditableField<string>
  currency: AuditableField<string>
  ratio: AuditableField<RatioValue>
  attributed_cost_per_share: AuditableField<string>
}

export interface ClassificationSignal {
  supports: EventType
  rationale: string
  source: SourceEvidence
}

export interface ClassificationConflict {
  description: string
  signals: ClassificationSignal[]
}

export interface CorporateAction {
  event_type: AuditableField<EventType>
  classification_evidence: ClassificationSignal[]
  classification_conflicts: ClassificationConflict[]
  dates: EventDates
  financials: Financials
}

export interface ReferenceRecord {
  issuer: string
  cnpj: string
  isin: string
  ticker: string
  share_class: string
  listing_segment: string
  status: string
}

export interface ReferenceConflict {
  code: string
  field: string
  expected?: JsonValue
  observed?: JsonValue
}

export interface ReferenceValidation {
  exact_match: boolean
  matched_by: string[]
  reference_record: ReferenceRecord | null
  conflicts: ReferenceConflict[]
  possible_matches: ReferenceRecord[]
}

export interface RoutingReason {
  code: string
  category: string
  message: string
}

export interface ExtractionAttempt {
  strategy: ExtractionStrategy
  outcome: ExtractionAttemptOutcome
  pass_number: number | null
  model: string | null
  unresolved_fields: string[]
  error: string | null
}

export interface PreliminaryCheck {
  code: string
  passed: boolean
  message: string
}

export interface DocumentRecord {
  schema_version: '2.0'
  document_id: string
  source_document: SourceDocument
  processing_status: ProcessingStatus
  issuer: {
    name: AuditableField<string>
    cnpj: AuditableField<string>
  }
  security: {
    isin: AuditableField<string>
    ticker: AuditableField<string>
    share_class: AuditableField<string>
    listing_segment: AuditableField<string>
    asset_status: AuditableField<string>
  }
  corporate_action: CorporateAction
  extraction_attempts: ExtractionAttempt[]
  preliminary_checks: PreliminaryCheck[]
  document_confidence: {
    score: number
    completion_percentage: number
    required_fields: string[]
    resolved_fields: string[]
    missing_fields: string[]
    rationale: string
  }
  reference_validation: ReferenceValidation
  validations: ValidationResult[]
  review: { required: boolean; reasons: RoutingReason[] }
  follow_up: { required: boolean; reasons: RoutingReason[] }
  exceptions: RoutingReason[]
}

export interface ExceptionReportDocument {
  document_id: string
  file_name: string
  processing_status: ProcessingStatus
  confidence_score: number | null
  exceptions: RoutingReason[]
}

export interface ExceptionReport {
  schema_version: '2.0'
  summary: {
    processed: number
    accepted: number
    human_review: number
    pending_information: number
    failed: number
  }
  documents: ExceptionReportDocument[]
}

export interface BatchUploadResponse {
  records: DocumentRecord[]
  report: ExceptionReport
}

export interface HealthResponse {
  status: string
  provider: string
  provider_configured: boolean
  golden_records_available: boolean
  database_configured: boolean
}
