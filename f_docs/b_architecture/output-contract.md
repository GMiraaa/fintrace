# FinTrace — Contrato de saída v2

Este é o contrato normativo para os modelos Pydantic, persistência em JSON e
respostas da API. A saída principal da LLM é um subconjunto deste contrato;
validação, confiança e roteamento são preenchidos pelo backend.

O artefato normativo do case continua sendo o JSON no filesystem. PostgreSQL
mantém cache e histórico, e a resposta HTTP acrescenta metadados de upload, mas
nenhuma dessas projeções altera o schema `2.0` do registro por documento.

## Convenções

- `schema_version`: `2.0`.
- Datas: strings ISO 8601 (`YYYY-MM-DD`).
- Decimais: strings, por exemplo `"0.1738420000"` e `"17.5"`.
- Ausência de valor: `null`, nunca zero ou string vazia.
- Evidência literal deve ser curta e suficiente para localizar a informação.
- Páginas são numeradas a partir de 1.
- Campos não aplicáveis continuam presentes com `value: null` e
  `status: NOT_APPLICABLE`.

## Enums

### EventType

`DIVIDEND`, `JCP`, `BONUS_SHARES`, `STOCK_SPLIT`, `REVERSE_SPLIT`, `OTHER`,
`UNKNOWN`.

### FieldStatus

`EXTRACTED`, `REFERENCE_ENRICHED`, `DERIVED`, `NOT_DISCLOSED`,
`NOT_APPLICABLE`, `AMBIGUOUS`, `CONFLICT`, `UNREADABLE`, `UNKNOWN`.

### Origin

`DOCUMENT`, `REFERENCE`, `DERIVED`, `UNKNOWN`.

### Confiança

`confidence` e `agent_agreement` são inteiros de `0` a `100`. O segundo pode
ser `null` quando não houve múltiplas passagens de IA para comparar.

### ExtractionMethod

`NATIVE_TEXT`, `OCR`.

### ValidationStatus

`PASS`, `WARN`, `FAIL`, `NOT_APPLICABLE`, `NOT_EVALUATED`.

### ProcessingStatus

`ACCEPTED`, `REVIEW_REQUIRED`, `PENDING_INFORMATION`, `FAILED`.

### ExtractionStrategy

`PYTHON`, `BASIC_LLM`, `STRONG_LLM`.

### ExtractionAttemptOutcome

`SUFFICIENT`, `INSUFFICIENT`, `ERROR`.

### ExceptionCategory

`BUSINESS_EXCEPTION`, `VALIDATION_EXCEPTION`, `REVIEW_EXCEPTION`,
`TECHNICAL_ERROR`.

### TaxTreatment

`NOT_APPLICABLE`, `TAX_EXEMPT`, `TAX_RULE_UNIFORM`,
`TAX_DEPENDS_ON_BENEFICIARY`, `UNKNOWN`.

## Estruturas reutilizáveis

Todo campo auditável possui:

```json
{
  "value": null,
  "status": "UNKNOWN",
  "origin": "UNKNOWN",
  "confidence": 0,
  "agent_agreement": null,
  "sources": [],
  "validation": []
}
```

A justificativa da confiança é composta, e não armazenada em uma frase livre:

- `status` informa se o valor foi extraído, enriquecido, derivado, omitido pelo
  emissor, considerado ambíguo ou conflitante;
- `origin` identifica documento, referência ou derivação;
- `agent_agreement` quantifica quantas passagens convergiram para o valor/status
  dominante;
- `sources` preserva página, trecho literal e método de extração;
- `validation` reúne as regras que afetaram especificamente o campo.

Essa decomposição permite reconstruir deterministicamente o percentual do
campo, sem depender de uma justificativa textual produzida por LLM.

Uma fonte possui:

```json
{
  "page": 1,
  "evidence": "Código de negociação TIET3",
  "extraction_method": "NATIVE_TEXT"
}
```

Um resultado de validação possui:

```json
{
  "rule": "REF_ISIN_MATCH",
  "status": "PASS",
  "message": "ISIN matches the reference record.",
  "expected": "BRTIETACNOR3",
  "observed": "BRTIETACNOR3"
}
```

`expected` e `observed` aceitam qualquer valor JSON e são opcionais.

Na interface, a justificativa de confiança é apresentada a partir desses
elementos determinísticos. Ela não é um novo dado produzido pela LLM nem altera
o JSON persistido.

## Registro por documento

```json
{
  "schema_version": "2.0",
  "document_id": "sha256:...",
  "source_document": {
    "file_name": "notice.pdf",
    "sha256": "...",
    "page_count": 1,
    "extraction_methods": ["NATIVE_TEXT"]
  },
  "processing_status": "REVIEW_REQUIRED",
  "issuer": {
    "name": {},
    "cnpj": {}
  },
  "security": {
    "isin": {},
    "ticker": {},
    "share_class": {},
    "listing_segment": {},
    "asset_status": {}
  },
  "corporate_action": {
    "event_type": {},
    "classification_evidence": [],
    "classification_conflicts": [],
    "dates": {
      "approval_date": {},
      "record_date": {},
      "ex_date": {},
      "payment_date": {},
      "credit_date": {},
      "fraction_period_start": {},
      "fraction_period_end": {}
    },
    "financials": {
      "gross_amount_per_share": {},
      "net_amount_per_share": {},
      "tax_rate_percent": {},
      "tax_treatment": {},
      "currency": {},
      "ratio": {},
      "attributed_cost_per_share": {}
    }
  },
  "extraction_attempts": [
    {
      "strategy": "BASIC_LLM",
      "outcome": "INSUFFICIENT",
      "pass_number": 1,
      "model": "gemini-3.5-flash-lite",
      "unresolved_fields": ["corporate_action.event_type"],
      "error": null
    },
    {
      "strategy": "BASIC_LLM",
      "outcome": "INSUFFICIENT",
      "pass_number": 2,
      "model": "gemini-3.5-flash-lite",
      "unresolved_fields": ["corporate_action.event_type"],
      "error": null
    },
    {
      "strategy": "STRONG_LLM",
      "outcome": "SUFFICIENT",
      "pass_number": 3,
      "model": "gemini-3.8-flash",
      "unresolved_fields": [],
      "error": null
    }
  ],
  "preliminary_checks": [
    {
      "code": "AGENT_CONSENSUS",
      "passed": false,
      "message": "Divergência ou ausência de consenso em: corporate_action.event_type"
    },
    {
      "code": "CLASSIFICATION_CONSISTENCY",
      "passed": false,
      "message": "Falharam as regras: EVENT_UNKNOWN"
    }
  ],
  "document_confidence": {
    "score": 88,
    "completion_percentage": 100,
    "required_fields": [
      "issuer.name",
      "security.isin",
      "security.ticker",
      "corporate_action.event_type",
      "corporate_action.dates.approval_date",
      "corporate_action.dates.record_date",
      "corporate_action.dates.ex_date",
      "corporate_action.dates.payment_date",
      "corporate_action.financials.gross_amount_per_share",
      "corporate_action.financials.currency"
    ],
    "resolved_fields": [
      "issuer.name",
      "security.isin",
      "security.ticker",
      "corporate_action.event_type",
      "corporate_action.dates.approval_date",
      "corporate_action.dates.record_date",
      "corporate_action.dates.ex_date",
      "corporate_action.dates.payment_date",
      "corporate_action.financials.gross_amount_per_share",
      "corporate_action.financials.currency"
    ],
    "missing_fields": [],
    "rationale": "10 de 10 campos materiais foram resolvidos..."
  },
  "reference_validation": {
    "exact_match": false,
    "matched_by": [],
    "reference_record": null,
    "conflicts": [],
    "possible_matches": []
  },
  "validations": [],
  "review": {
    "required": true,
    "reasons": []
  },
  "follow_up": {
    "required": false,
    "reasons": []
  },
  "exceptions": []
}
```

Cada `{}` dentro de `issuer`, `security`, `event_type`, `dates` e
`financials` representa a estrutura de campo auditável. O tipo de `value`
depende do campo:

- Identificadores, moeda, tax treatment e datas: `string | null`.
- Valores monetários e taxa: `decimal string | null`.
- `event_type`: `EventType | null`.
- `ratio`: objeto abaixo ou `null`.

`extraction_attempts` preserva a ordem real da cascata. Estratégias não
executadas não aparecem. Uma tentativa com `ERROR` registra uma mensagem
técnica e permite que a próxima estratégia seja tentada; os campos já extraídos
continuam preservados.

`preliminary_checks` registra o resultado obtido depois das duas passagens
básicas e antes da decisão de escalada. Os códigos cobrem campos obrigatórios,
consenso, grounding, golden records, datas, valores, classificação e OCR.

`document_confidence` resume a cobertura dos campos materiais. O `score` é a
média dos percentuais dos campos materiais; ausências contribuem com zero. A
`completion_percentage` considera apenas presença ou ausência. As listas tornam
o cálculo auditável e um score abaixo de 75 exige revisão humana. O percentual
não representa uma probabilidade estatística produzida pela LLM.

Com chave configurada, há duas tentativas `BASIC_LLM`. `STRONG_LLM` é a terceira
passagem quando qualquer check preliminar falha e possui as function callings.
`PYTHON` só aparece sem chave ou após indisponibilidade de todas as tentativas de IA.

```json
{
  "kind": "NEW_PER_EXISTING",
  "numerator": "1",
  "denominator": "20",
  "percentage": "5"
}
```

`ratio.kind` aceita:

- `NEW_PER_EXISTING`: novas ações por ações existentes, usado em bonificação.
- `RESULTING_PER_EXISTING`: ações resultantes por ações existentes, usado em
  grupamento e desdobramento.

## Classificação do evento

Cada sinal que sustenta a classificação preserva o tipo indicado, a explicação
determinística ou contextual e a evidência documental:

```json
{
  "supports": "DIVIDEND",
  "rationale": "Termo econômico explícito identificado no documento.",
  "source": {
    "page": 1,
    "evidence": "Dividendos",
    "extraction_method": "NATIVE_TEXT"
  }
}
```

Quando sinais materiais sustentam classificações incompatíveis, o conflito não
é resolvido silenciosamente. Ele é preservado com uma descrição e os sinais que
o originaram:

```json
{
  "description": "Título e corpo indicam eventos diferentes.",
  "signals": [
    {
      "supports": "DIVIDEND",
      "rationale": "Classificação indicada no título.",
      "source": {
        "page": 1,
        "evidence": "Aviso de dividendos",
        "extraction_method": "NATIVE_TEXT"
      }
    },
    {
      "supports": "JCP",
      "rationale": "Substância econômica descrita no corpo.",
      "source": {
        "page": 1,
        "evidence": "juros sobre o capital próprio",
        "extraction_method": "NATIVE_TEXT"
      }
    }
  ]
}
```

## Referência

`matched_by` aceita `issuer`, `cnpj`, `isin`, `ticker` e `share_class`.
`reference_record` preserva os campos canônicos da referência. `conflicts`
expõe divergências sem substituir silenciosamente o valor do documento.
`possible_matches` é somente sugestivo.

## Projeção operacional no frontend

O frontend não cria nem modifica resultados de domínio. Ele projeta este
contrato para auditoria da seguinte forma:

| Necessidade do operador | Elementos do contrato apresentados |
|---|---|
| O que foi extraído | `value` e `status` |
| De onde veio | `origin`, `sources.page`, `sources.evidence` e `extraction_method` |
| Quão confiável é | `confidence`, `agent_agreement` e metadados do campo |
| Qual a cobertura geral | `document_confidence.score`, completude e campos ausentes |
| Como foi validado | `validation`, `expected`, `observed` e `reference_validation` |
| O que exige atuação | `processing_status`, `review`, `follow_up` e `exceptions` |
| Como a cascata se comportou | `extraction_attempts` e `preliminary_checks` |

O tipo do evento também é tratado como campo auditável, acompanhado por
`classification_evidence` e `classification_conflicts`. O golden record é
exibido em bloco próprio para não ser confundido com evidência documental.

O botão de visualização usa o `document_id` para consultar
`GET /api/documents/{document_id}/file`. Essa rota é complementar ao contrato:
o JSON permanece suficiente para a auditoria cotidiana, enquanto o PDF fica
disponível para investigação ou conferência visual.

Cada JSON escrito no filesystem também é inserido integralmente em JSONB na
tabela `processing_artifacts`. As colunas `artifact_type`, `file_name`,
`document_id`, `processing_status` e `created_at` permitem consultas sem
desmontar o payload. Cada nova execução cria uma linha e preserva o histórico.

Separadamente, `documents` é o índice operacional por conteúdo. `sha256` é sua
chave primária, `document_id` também é único e os campos
`processing_state`, `latest_processing_status`, `latest_payload`, `revision`,
`processing_started_at`, `processed_at` e `updated_at` controlam deduplicação e
reavaliação. `latest_payload` facilita reutilização, mas não substitui as linhas
imutáveis de `processing_artifacts`.

## Contrato HTTP de upload e reavaliação

`POST /api/documents/upload` e
`POST /api/documents/{document_id}/reevaluate` retornam:

```json
{
  "records": [],
  "report": {
    "schema_version": "2.0",
    "summary": {
      "processed": 0,
      "accepted": 0,
      "human_review": 0,
      "pending_information": 0,
      "failed": 0
    },
    "documents": []
  },
  "uploads": [
    {
      "file_name": "aviso.pdf",
      "sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
      "disposition": "REUSED",
      "message": "Documento já processado; resultado anterior reutilizado sem nova chamada à IA."
    }
  ]
}
```

As disposições possíveis são:

- `PROCESSED`: a requisição reservou um hash novo e executou a pipeline;
- `REUSED`: o último `DocumentRecord` concluído foi devolvido sem nova LLM;
- `DUPLICATE_IN_BATCH`: outro arquivo do mesmo lote possui bytes idênticos;
- `ALREADY_PROCESSING`: outra requisição já reservou o SHA-256;
- `REEVALUATED`: o operador solicitou nova execução para um documento concluído.

O nome não participa da identidade. A reserva usa a unicidade do SHA-256 no
PostgreSQL, portanto dois uploads simultâneos do mesmo conteúdo não iniciam duas
chamadas à IA. Uma reavaliação preserva o hash, incrementa `revision` e cria
novo artefato histórico; se o documento estiver em `PROCESSING`, a API retorna
`409`.

## Códigos de validação

### Documento e referência

- `REF_NO_MATCH`
- `REF_STRONG_IDENTIFIER_CONFLICT`
- `REF_ISSUER_MATCH`, `REF_ISSUER_CONFLICT`
- `REF_ISIN_MATCH`, `REF_ISIN_CONFLICT`
- `REF_CNPJ_MATCH`, `REF_CNPJ_CONFLICT`
- `REF_TICKER_MATCH`, `REF_TICKER_CONFLICT`
- `REF_SHARE_CLASS_MATCH`, `REF_SHARE_CLASS_CONFLICT`
- `REF_ASSET_INACTIVE`

### Datas

- `DATE_APPROVAL_AFTER_RECORD`
- `DATE_RECORD_NOT_BEFORE_EX`
- `DATE_PAYMENT_BEFORE_RECORD`
- `DATE_PAYMENT_NOT_DISCLOSED`

### Valores financeiros

- `FIN_GROSS_NET_TAX_CONSISTENT`
- `FIN_GROSS_NET_TAX_MISMATCH`
- `FIN_TAX_DEPENDS_ON_BENEFICIARY`
- `FIN_UNIVERSAL_NET_NOT_APPLICABLE`
- `FIN_CURRENCY_MISSING`
- `FIN_RATIO_VALID`, `FIN_RATIO_INVALID`

### Evento

- `EVENT_CLASSIFICATION_SUPPORTED`
- `EVENT_CLASSIFICATION_CONFLICT`
- `EVENT_REQUIRED_FIELD_MISSING`
- `EVENT_UNKNOWN`

## Códigos de roteamento e exceção

- `EXTRACTION_CASCADE_EXHAUSTED`

Cada reason ou exception possui `code`, `category` e `message`.

### Acompanhamento de negócio

- `PAYMENT_DATE_NOT_DISCLOSED` — `BUSINESS_EXCEPTION`

### Validação

- `REFERENCE_NOT_FOUND` — `VALIDATION_EXCEPTION`
- `REFERENCE_IDENTIFIER_CONFLICT` — `VALIDATION_EXCEPTION`
- `DATE_SEQUENCE_INCONSISTENT` — `VALIDATION_EXCEPTION`
- `FINANCIAL_VALUES_INCONSISTENT` — `VALIDATION_EXCEPTION`

### Revisão humana

- `EVENT_CLASSIFICATION_AMBIGUOUS` — `REVIEW_EXCEPTION`
- `TITLE_BODY_CLASSIFICATION_CONFLICT` — `REVIEW_EXCEPTION`
- `CRITICAL_FIELD_CONFIDENCE_BELOW_THRESHOLD` — `REVIEW_EXCEPTION`
- `DOCUMENT_CONFIDENCE_BELOW_THRESHOLD` — `REVIEW_EXCEPTION`
- `DOCUMENT_PARTIALLY_UNREADABLE` — `REVIEW_EXCEPTION`

### Erro técnico

- `PDF_CORRUPT` — `TECHNICAL_ERROR`
- `OCR_FAILED` — `TECHNICAL_ERROR`
- `LLM_PROVIDER_UNAVAILABLE` — `TECHNICAL_ERROR`
- `LLM_STRUCTURED_OUTPUT_INVALID` — `TECHNICAL_ERROR`
- `OUTPUT_WRITE_FAILED` — `TECHNICAL_ERROR`
- `PROCESSING_FAILED` — `TECHNICAL_ERROR`

## Precedência de roteamento

1. Erro técnico irrecuperável: `FAILED`.
2. Razão de revisão humana: `REVIEW_REQUIRED`.
3. Informação material explicitamente pendente: `PENDING_INFORMATION`.
4. Nenhum bloqueio: `ACCEPTED`.

`PENDING_INFORMATION` não implica `review.required: true`. Um documento pode
ter alta confiança de que a informação não foi divulgada e exigir apenas
acompanhamento posterior.

## Artefato de falha técnica

Quando uma falha técnica impede a criação do registro completo, o JSON do
documento contém `schema_version`, `document_id`, `file_name`,
`processing_status: FAILED` e a lista de exceções. Isso preserva o princípio de
um artefato por documento mesmo para PDFs corrompidos ou falhas de provider.

## Relatório consolidado

O relatório usa o mesmo `schema_version` e contém:

```json
{
  "schema_version": "2.0",
  "summary": {
    "processed": 0,
    "accepted": 0,
    "human_review": 0,
    "pending_information": 0,
    "failed": 0
  },
  "documents": [
    {
      "document_id": "sha256:...",
      "file_name": "notice.pdf",
      "processing_status": "ACCEPTED",
      "confidence_score": 92,
      "exceptions": []
    }
  ]
}
```
