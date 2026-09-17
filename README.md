<p align="center">
  <img src="b_frontend/public/brand/fintrace-logo.png" alt="FinTrace" width="520">
</p>

# FinTrace

FinTrace é uma plataforma de processamento de eventos corporativos apoiada por
automação determinística e IA, projetada para transformar avisos financeiros
heterogêneos em registros
estruturados, validados e auditáveis.

A plataforma processa PDFs nativos e escaneados e, quando uma chave de API está
configurada, envia todos os documentos primeiro a um agente de IA econômico.
Um modelo mais forte, apoiado por function calling, trata as pendências. Python
é a contingência de extração quando não há chave ou o provider está
indisponível. Em seguida, o pipeline valida o resultado e encaminha incertezas
materiais para um operador humano. Cada campo relevante preserva
valor, status, origem, confiança, evidência e resultados de validação.

> IA onde interpretação é necessária. Código onde determinismo é possível.

## Problema resolvido

Avisos de eventos corporativos utilizam layouts e terminologias variadas. O
título pode até contradizer a substância econômica descrita no corpo do
documento. Uma extração incorreta pode alterar o tratamento tributário, o
cronograma de pagamentos e operações posteriores de custódia.

Por isso, o FinTrace não trata a resposta da LLM como verdade. A plataforma
separa:

- Interpretação da linguagem não estruturada;
- Validação determinística de identidade, datas, valores e tipo de evento;
- Dados de referência conhecidos;
- Cálculo de confiança e revisão humana baseada em risco.

O sistema prefere `UNKNOWN` a um valor inventado e diferencia uma extração
incerta de uma informação explicitamente marcada como ainda não divulgada.

## Atendimento ao enunciado

| Requisito mínimo | Como é atendido | Evidência principal |
|---|---|---|
| 1. Campos obrigatórios | Emissor, CNPJ, ISIN, ticker, tipo, datas, valores, proporção e moeda possuem campos tipados e auditáveis. A data de aprovação participa dos campos materiais. | `models/schemas.py`, `agent/schemas.py` e contrato de saída |
| 2. Classificação do evento | A LLM interpreta a substância econômica; regras posteriores verificam sinais, campos exigidos e conflito entre título e corpo. | `agent`, `tools/event_rules.py` e `classification_evidence` |
| 3. Golden records e coerência | O modelo forte dispõe de `lookup_golden_record` por function calling. O backend sempre repete a validação canônica e aplica regras de datas, valores e evento. | `agent/reference_tool.py`, `agent/preliminary.py` e `tools` |
| 4. Confiança e rastreabilidade | Cada campo registra percentual, concordância entre passagens, origem, página, trecho, método de leitura e validações; o documento recebe score e completude. | `confidence` e schema `2.0` |
| 5. Roteamento de incerteza | Campos materiais abaixo de 75%, conflitos, falhas de regra e baixa legibilidade geram motivos estruturados e revisão humana. Informação futura segue para acompanhamento. | `routing/router.py` e `exception_report.json` |
| 6. Saída auditável | Cada documento gera um JSON, inclusive em falha técnica, e o lote gera um relatório curto. A interface projeta valor, evidência, confiança, referência e ação necessária. | `a_data/b_output`, contrato de saída e frontend |

Os entregáveis do case são complementares: o código executável, este README com
decisões e trade-offs, e os artefatos efetivamente gerados para o lote. O
PostgreSQL preserva histórico operacional, mas **não substitui** os JSONs e o
relatório versionados em `a_data/b_output` na entrega.

## Fluxo de processamento

```mermaid
flowchart TD
    A[Upload de um ou mais PDFs] --> B[Validação de extensão, MIME, tamanho e assinatura]
    B --> HASH[SHA-256 calculado a partir do conteúdo]
    HASH --> CLAIM{Reserva atômica no PostgreSQL}
    CLAIM -- Resultado concluído --> CACHE[Reutiliza o último registro<br/>sem chamar a IA]
    CLAIM -- Outro upload processando --> WAIT[Informa processamento em andamento]
    CLAIM -- Hash novo --> C{Texto nativo suficiente?}
    C -- Sim --> D[Normalização por página]
    C -- Não --> E[Renderização a 300 DPI]
    E --> F[Cinza, contraste, redução de ruído, nitidez e Otsu]
    F --> G[Tesseract: duas versões da página]
    G --> D
    D --> H{Chave de IA configurada?}
    H -- Sim --> J1[Gemini básico: passagem 1]
    H -- Não --> X[Contingência em Python]
    J1 --> J2[Gemini básico: passagem 2 independente]
    J2 --> K[Consenso por campo e validação preliminar]
    K --> CHECK{Todos os checks passaram?}
    CHECK -- Não --> L[Gemini forte: passagem 3 e veredito]
    CHECK -- Sim --> M
    J1 -. indisponível .-> J2
    J2 -. indisponível .-> L
    L --> Z{Alguma IA respondeu validamente?}
    Z -- Sim --> M
    Z -- Não, todas indisponíveis --> X
    X --> M[Registro Pydantic]
    L -. function calling .-> T[Golden records e tools pdfplumber]
    M --> N[Validação canônica contra golden_records.csv]
    N --> O[Regras de datas, valores e classificação]
    O --> P[Confiança por campo e score do documento]
    P --> Q{Decisão}
    Q -->|Seguro| R[ACCEPTED]
    Q -->|Informação futura| S[PENDING_INFORMATION]
    Q -->|Incerteza ou conflito| U[REVIEW_REQUIRED]
    R --> V[JSON por documento e relatório consolidado]
    S --> V
    U --> V
    V --> DB[(Histórico PostgreSQL JSONB)]
    CACHE --> V
```

A LLM participa somente da interpretação. Validações financeiras, temporais,
de identidade, confiança e roteamento permanecem determinísticas, para que uma
resposta probabilística nunca tenha autoridade final sobre o registro.

O modelo forte pode consultar a referência e o PDF por function calling.
Independentemente de a LLM ter sido acionada, todo registro passa
obrigatoriamente pelas funções determinísticas de referência e coerência do
pipeline antes de receber confiança e decisão operacional.

## Tecnologias e justificativas

- **React + TypeScript + Vite:** mantém a interface operacional pequena e
  rápida, com o contrato da API tipado em modo estrito.
- **FastAPI:** fornece upload multipart tipado e documentação OpenAPI.
- **Pydantic v2:** é a fonte de verdade dos contratos estruturados.
- **PyMuPDF:** extrai texto nativo antes de qualquer tentativa de OCR.
- **Tesseract + Pillow:** processam localmente e de forma seletiva páginas
  compostas por imagens, com escala de cinza, autocontraste, redução de ruído,
  nitidez e binarização antes do reconhecimento.
- **Gemini:** é o provider inicial porque sua camada gratuita oferece saída
  estruturada. O `gemini-3.5-flash-lite` atua como modelo básico e o
  `gemini-3.8-flash` como modelo forte. A integração fica atrás de um protocolo
  pequeno e pode ser substituída sem alterar as regras determinísticas.
- **`Decimal` do Python:** evita erros de ponto flutuante binário em cálculos
  financeiros.
- **PostgreSQL + JSONB:** preserva o histórico de todos os JSONs gerados sem
  retirar do filesystem os artefatos diretamente avaliados no case.
- **CSV:** mantém a pequena base de referência simples e inspecionável.

A camada gratuita do Gemini pode utilizar o conteúdo enviado para aprimorar produtos
do Google. Ele é adequado ao conjunto de dados sintético fornecido; os termos do
provider e a governança de dados devem ser reavaliados antes do processamento de
documentos confidenciais em produção.

## Arquitetura e separação de responsabilidades

```mermaid
flowchart LR
    UI[React / TypeScript / Vite] -->|HTTP multipart e JSON| API[FastAPI]
    API --> REG[Registro por SHA-256<br/>reserva atômica e cache]
    REG --> PG[(PostgreSQL)]
    API --> PIPE[Pipeline de processamento]
    PIPE --> DOC[Pré-processamento<br/>PyMuPDF, Pillow e Tesseract]
    PIPE --> CASCADE[Cascata de extração<br/>Gemini básico, forte e contingência Python]
    CASCADE --> REFTOOL[Function calling<br/>golden records]
    CASCADE --> PDFTOOL[Function calling<br/>pdfplumber]
    PIPE --> RULES[Regras determinísticas<br/>referência, datas e valores]
    PIPE --> CONF[Confiança e roteamento]
    REFTOOL --> CSV[(golden_records.csv)]
    RULES --> CSV
    PIPE --> JSON[(JSONs e relatório)]
    PIPE --> PG
```

Essa estrutura foi escolhida para manter limites claros:

- O frontend apresenta upload, andamento, evidências e exceções; ele não contém
  regra financeira nem decide confiança;
- A API valida a fronteira HTTP e delega o trabalho ao pipeline;
- O pipeline define a ordem das etapas e impede que o provider controle o fluxo;
- `documents` trata somente leitura, melhoria de imagem e OCR;
- `agent` interpreta o conteúdo e expõe integrações controladas ao provider;
- `tools`, `confidence` e `routing` concentram decisões determinísticas de
  validação, confiança e encaminhamento que podem ser testadas isoladamente;
- Os modelos Pydantic formam o contrato único usado pela API, persistência e
  frontend;
- Dados de entrada, referência e saída ficam separados para evitar que o golden
  record seja confundido com um documento submetido.

Para o escopo do case, essa divisão oferece auditabilidade sem introduzir filas
ou orquestração distribuída, mas preserva o histórico dos resultados no banco.

## Estrutura do repositório

```text
fintrace/
├── a_data/
│   ├── a_input/                  # PDFs fornecidos e documentos enviados
│   ├── b_output/                 # JSONs e relatório de exceções
│   └── c_golden_records/
│       └── golden_records.csv
├── b_frontend/                   # Interface React/TypeScript por componentes
│   └── public/brand/             # Logo e ativos estáticos versionados
├── c_backend/
│   ├── src/
│   │   ├── agent/                # Adaptador do provider e mapeamento da extração
│   │   ├── api/                  # Segurança de upload e contratos HTTP
│   │   ├── confidence/           # Motor determinístico de confiança
│   │   ├── documents/            # Extração nativa e OCR
│   │   ├── models/               # Contratos de domínio em Pydantic
│   │   ├── pipeline/             # Orquestração e persistência
│   │   ├── persistence/          # Artefatos JSON no PostgreSQL
│   │   ├── routing/              # Revisão e relatório de exceções
│   │   └── tools/                # Regras de referência, datas, valores e eventos
│   └── tests/
├── d_skills/corporate_actions/   # Conhecimento procedural de Asset Servicing
├── .skills/b_backend_skills/     # Skill complementar de extração de PDFs
├── e_scripts/                    # Scripts do ciclo de vida Docker
├── f_docs/b_architecture/        # Contratos e decisões arquiteturais
└── docker-compose.yml
```

Arquivos de marca devem permanecer em `b_frontend/public/brand`. A pasta
`b_frontend/dist` é gerada pelo Vite, está ignorada pelo Git e pode ser
substituída integralmente a cada build; portanto, não deve ser usada como origem
de imagens ou outros ativos permanentes.

## Configuração

Copie o arquivo de exemplo. Com uma chave Gemini, a IA passa a ser o caminho
principal de todos os documentos:

```bash
cp .env.example .env
```

Configuração dos modelos:

```dotenv
LLM_PROVIDER=gemini
LLM_BASIC_MODEL=gemini-3.5-flash-lite
LLM_STRONG_MODEL=gemini-3.8-flash
GEMINI_API_KEY=sua-chave
DATABASE_URL=postgresql://fintrace:fintrace@localhost:5432/fintrace
```

Variáveis opcionais importantes:

| Variável | Padrão | Finalidade |
|---|---:|---|
| `MAX_UPLOAD_SIZE_MB` | `20` | Tamanho máximo de cada PDF |
| `OCR_LANGUAGE` | `por` | Idioma utilizado pelo Tesseract |
| `OCR_DPI` | `300` | Resolução usada para renderizar páginas antes do OCR |
| `NATIVE_TEXT_MIN_CHARS` | `80` | Limiar por página antes de acionar OCR |
| `LLM_BASIC_MODEL` | `gemini-3.5-flash-lite` | Agente principal para todos os PDFs |
| `LLM_STRONG_MODEL` | `gemini-3.8-flash` | Agente de escalonamento com tools |
| `DATABASE_URL` | PostgreSQL local | Persistência dos artefatos JSON em JSONB |
| `BACKEND_PORT` | `8000` | Porta da API no host |
| `FRONTEND_PORT` | `5173` | Porta da interface no host |
| `LOG_LEVEL` | `INFO` | Nível dos logs estruturados do backend |

Não faça commit do `.env`; ele está ignorado pelo Git.

Sem uma chave do Gemini, ou quando todas as tentativas de IA falham por
indisponibilidade do provider, a extração Python entra como contingência.

## Estratégia de extração em cascata

Com uma chave configurada, a ordem de execução é:

1. O modelo básico analisa o PDF duas vezes, com instruções independentes;
2. As respostas são comparadas campo a campo. Valores e status iguais geram
   consenso; divergências são preservadas para adjudicação;
3. Antes de escalar, o backend verifica campos materiais, grounding das
   evidências, referência, datas, cálculos, classificação e qualidade do OCR;
4. Se qualquer check falhar, o modelo forte recebe o documento, o resultado
   consolidado e os motivos objetivos da escalada como terceira passagem;
5. O modelo forte consulta golden records e relê texto, tabelas ou
   coordenadas do PDF por function calling;
6. O resultado consolidado passa novamente pelas regras determinísticas e, se ainda não
   for seguro, segue para revisão humana.

Python não é executado depois de uma resposta válida, porém incompleta, dos
modelos: esse cenário representa incerteza real e segue para revisão. A
contingência local é reservada à ausência de chave ou indisponibilidade das
tentativas de IA.

O modelo forte funciona como adjudicador das divergências entre as duas
passagens básicas. Seu veredito não ignora a discordância: o percentual
`agent_agreement` continua registrando o nível de consenso observado. Conflitos
que permanecerem após a validação final seguem para revisão humana.

Cada JSON registra `extraction_attempts` e `preliminary_checks`, informando
passagens, modelos, campos pendentes, erros e os checks que justificaram ou não
a chamada do modelo forte.

Os checks preliminares são: campos obrigatórios, consenso dos agentes,
evidence grounding, validação contra golden records, coerência de datas,
coerência financeira, consistência da classificação e qualidade do OCR.

### Preparação local para OCR

Quando uma página não possui texto nativo suficiente, ela é renderizada a 300
DPI. O backend gera duas versões para o Tesseract:

- Escala de cinza com autocontraste, filtro de mediana e nitidez;
- Versão binária com limiar calculado pelo método de Otsu.

O texto das duas tentativas é pontuado pela quantidade de caracteres e palavras
úteis, e a melhor resposta compõe o texto normalizado enviado ao agente. OCR e
melhoria de imagem continuam locais para reduzir ruído e uso desnecessário de
tokens, mas a interpretação principal é feita pela IA.

### Tool de validação da referência

No escalonamento para o modelo forte, o SDK disponibiliza a função
`lookup_golden_record`. O modelo pode consultar emissor, CNPJ, ISIN, ticker e
classe diretamente na base canônica. O retorno contém correspondências,
conflitos e possíveis registros.

A consulta feita pelo agente não substitui a validação do pipeline: o backend
repete o cruzamento depois da extração e permanece como autoridade final. Dados
da referência nunca são apresentados como evidência extraída do documento.

A function calling é uma capacidade do agente forte; a validação determinística
posterior continua obrigatória para todos os registros.

### Tools de leitura com pdfplumber

Quando o texto normalizado não preserva suficientemente uma tabela ou relação
de layout, a LLM pode chamar três funções controladas pelo backend:

- `extract_pdf_text`: recupera texto de um intervalo de páginas, com opção de
  preservar o layout;
- `extract_pdf_tables`: extrai as tabelas de uma página;
- `inspect_pdf_words`: retorna palavras e suas caixas delimitadoras.

As funções ficam vinculadas ao PDF que está sendo processado. O agente informa
somente páginas e opções de extração; ele não fornece caminhos e não recebe
acesso genérico ao filesystem, execução de código ou MCP. Os retornos também
possuem limites de tamanho para evitar contexto excessivo.

### Skills carregadas pelo agente

Quando a cascata aciona uma LLM, o backend monta a instrução de sistema com:

- A skill de eventos corporativos em `d_skills/corporate_actions`;
- A skill complementar de extração de PDFs em
  `.skills/b_backend_skills/.agents/skills/pdf-extraction`.

O conteúdo de ambas é carregado integralmente na criação do pipeline. A skill
de PDF orienta a interpretação das function callings de texto, tabelas e
layouts; a leitura nativa, a melhoria de imagem e o OCR continuam sendo
executados deterministicamente pelo backend antes da chamada ao agente.

## Execução com Docker

Construa e inicie frontend, backend e PostgreSQL:

```bash
./e_scripts/start.sh
```

Endereços disponíveis:

- Interface operacional: <http://localhost:5173>
- Documentação da API: <http://localhost:8000/docs>
- Health check: <http://localhost:8000/api/health>

Pare os containers sem removê-los:

```bash
./e_scripts/stop.sh
```

Remova containers e a rede da aplicação:

```bash
./e_scripts/remove.sh
```

Esses scripts nunca apagam `a_data/a_input`, `a_data/b_output`, os golden
records nem o volume `fintrace_postgres_data`. Os diretórios de arquivos ficam
montados a partir do host e os registros do banco sobrevivem à recriação dos
containers.

O script valida o Docker, inicia o banco, constrói as aplicações, aguarda o
backend ficar saudável e só termina quando o frontend também está em execução. O comando
Docker equivalente é:

```bash
docker compose up --build --detach --wait backend frontend
```

## Desenvolvimento local

Backend:

```bash
cd c_backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn src.main:app --reload
```

O Tesseract e o pacote do idioma português precisam estar instalados no host
para processar PDFs escaneados fora do Docker. O backend local também requer um
PostgreSQL acessível pela `DATABASE_URL`; a execução via Compose configura isso
automaticamente.

Frontend:

```bash
cd b_frontend
npm install
npm run dev
```

Durante o desenvolvimento local, o Vite encaminha `/api` para
`http://localhost:8000`.

## Processamento de documentos

A interface aceita um ou vários PDFs. O endpoint da API é:

```text
POST /api/documents/upload
Content-Type: multipart/form-data
Nome do campo: files
```

Exemplo:

```bash
curl -X POST http://localhost:8000/api/documents/upload \
  -F 'files=@a_data/a_input/02_banco_meridional_jcp.pdf'
```

Antes de acionar qualquer modelo, o backend calcula o SHA-256 dos bytes do PDF
e tenta reservar esse hash na tabela `documents`. A chave primária em `sha256`
torna a reserva atômica: uploads simultâneos do mesmo conteúdo podem ter nomes
diferentes, mas somente uma requisição conquista o direito de processá-lo. As
demais recebem `ALREADY_PROCESSING`; se já houver resultado concluído, recebem
`REUSED` junto do último registro, sem novas chamadas à IA.

A resposta inclui `uploads`, com o hash, a disposição e uma mensagem para cada
arquivo: `PROCESSED`, `REUSED`, `DUPLICATE_IN_BATCH` ou
`ALREADY_PROCESSING`. Assim, a interface explica quando houve economia de
processamento, sem confundir reutilização com uma nova análise.

O documento original de um registro processado pode ser consultado pelo seu
identificador de conteúdo:

```text
GET /api/documents/{document_id}/file
```

O endpoint valida o formato `sha256:<hash>` e localiza o PDF pelo conteúdo. Ele
não aceita caminho de arquivo informado pelo cliente. A interface usa essa rota
para exibir a primeira página como miniatura e, sob demanda, o documento no
visualizador completo. A resposta é
servida como `application/pdf`, com disposição `inline` e sem cache no navegador.
Identificadores inválidos, arquivos removidos ou hashes desconhecidos retornam
`404`.

Uma nova análise deliberada pode ser solicitada pelo botão `Reavaliar
documento` ou pelo endpoint:

```text
POST /api/documents/{document_id}/reevaluate
```

A reavaliação mantém o mesmo SHA-256, incrementa a revisão operacional e gera
um novo artefato no histórico. Se outra execução do documento estiver ativa, a
API retorna `409` em vez de iniciar uma segunda chamada concorrente.

### Uso do painel de resultados

Depois do processamento, a interface organiza o lote em uma sequência de
conferência:

1. A faixa superior resume aceites, revisões, acompanhamentos e falhas;
2. A fila de atenção leva diretamente aos documentos que exigem uma ação;
3. A navegação lateral seleciona o registro que será auditado;
4. O painel de decisão explica o resultado e a próxima ação esperada;
5. A aba `Visão geral` resume os controles e a conferência com a base oficial;
6. A aba `Dados extraídos` explica cada campo e permite abrir sua evidência;
7. A aba `Histórico da análise` reúne tentativas automáticas e regras aplicadas;
8. Uma miniatura mantém o PDF visível e permite abrir o visualizador completo;
9. `Reavaliar documento` executa novamente a cascata quando o operador desejar;
10. O relatório consolidado pode ser baixado pela ação `Baixar relatório do lote`.

A miniatura da primeira página é carregada para o documento selecionado. O
visualizador completo só é carregado quando solicitado. A trilha estruturada
continua sendo a fonte principal de auditoria, para que a conferência normal não
dependa da releitura integral do aviso.

Para processar todos os PDFs já presentes em `a_data/a_input` pelo ambiente do
backend:

```bash
cd c_backend
source .venv/bin/activate
python -m src.cli
```

Para reproduzir exatamente o lote entregue usando o Tesseract e as dependências
do container:

```bash
docker compose run --rm --no-deps backend python -m src.cli
```

Documentos específicos podem ser informados como argumentos posicionais.

## Entradas e saídas

Os uploads são sanitizados e validados por extensão, MIME type, tamanho e
assinatura do PDF antes de serem persistidos em `a_data/a_input`. O conteúdo é
identificado por SHA-256, independentemente do nome. Arquivos distintos com o
mesmo nome recebem sufixo único; cópias de conteúdo já registrado são removidas
depois que o banco confirma a reutilização, e exemplos existentes nunca são
sobrescritos.

`a_data/a_input` é um diretório operacional e está ignorado pelo Git para evitar
versionamento acidental de documentos potencialmente confidenciais. PDFs
recebidos fora da interface devem ser copiados para esse diretório antes da
execução da CLI. Os JSONs entregáveis em `a_data/b_output`, por outro lado, são
versionados.

Cada documento processado produz:

```text
a_data/a_input/exemplo.pdf
→ a_data/b_output/exemplo.json
```

Cada lote também atualiza:

```text
a_data/b_output/exception_report.json
```

O mesmo payload de cada JSON é inserido como uma nova linha na tabela
`processing_artifacts`, usando `JSONB`. A persistência é append-only: novos
processamentos do mesmo documento preservam o histórico, enquanto os arquivos
continuam sendo gerados para compor o entregável do case.

A tabela `documents` é o índice operacional. `sha256` é sua chave primária e,
portanto, única; ela guarda o estado `PROCESSING`, `COMPLETED` ou `FAILED`, o
último payload e o número da revisão. A tabela não substitui o histórico
append-only. Na inicialização, artefatos válidos produzidos antes da criação do
índice são incorporados ao registro, evitando reprocessamento desnecessário.

O JSON gerado utiliza o schema `2.0`. Valores decimais são representados como
strings e datas seguem ISO 8601. Consulte o
[contrato de saída](f_docs/b_architecture/output-contract.md) completo.

### Geração do lote entregável

Depois de configurar a chave e iniciar os serviços, processe uma única vez os
oito PDFs canônicos. Antes da entrega, `a_data/b_output` deve conter exatamente
os oito JSONs individuais e `exception_report.json`, sem artefatos de execuções
anteriores. O relatório é substituído a cada lote; o histórico completo permanece
no PostgreSQL.

Esta etapa faz parte da entrega e deve ser executada com os PDFs fornecidos
presentes em `a_data/a_input`. Para uma conferência rápida antes do envio:

```bash
find a_data/b_output -maxdepth 1 -type f -name '*.json' -printf '%f\n' | sort
```

O resultado esperado é um JSON por PDF do lote mais
`exception_report.json`. Não considere a entrega completa se esses arquivos
estiverem ausentes, mesmo que existam registros equivalentes no banco.

## Confiança e status dos campos

A confiança de cada campo é um inteiro entre `0` e `100`. Para valores vindos
do documento, o cálculo combina 70% da qualidade objetiva e 30% da concordância
entre as passagens do agente. A qualidade considera grounding, método de leitura
e validações. As bases atuais são:

- Evidência localizada em texto nativo: 92 pontos;
- Evidência localizada por OCR: 78 pontos;
- Referência confirmada: 95 pontos;
- Derivação com todas as regras aprovadas: 95 pontos;
- Informação explicitamente não divulgada com evidência: 95 pontos;
- Campo ambíguo, conflitante ou ilegível: 10 pontos;
- Regra relacionada reprovada: 15 pontos;
- Campo ausente ou desconhecido: 0 ponto.

`agent_agreement` registra separadamente o percentual de respostas que
convergiram para o valor/status dominante. Assim, o operador consegue distinguir
qualidade da evidência de estabilidade da interpretação do agente.

Esses critérios aparecem na aba `Dados extraídos`, antes da lista de campos. A
justificativa específica de cada valor permanece disponível ao expandir sua
linha.

O documento também recebe `document_confidence.score`, entre 0 e 100. Esse valor
não é uma probabilidade estatística da LLM: é a média dos percentuais dos
campos materiais, com campos ausentes valendo zero. O JSON preserva ainda a
porcentagem de completude e as listas de campos esperados,
resolvidos e ausentes. Score inferior a 75 encaminha o documento para revisão.

O status explica o que aconteceu com o campo independentemente da confiança.
Alguns exemplos são `EXTRACTED`, `REFERENCE_ENRICHED`, `DERIVED`,
`NOT_DISCLOSED`, `AMBIGUOUS`, `CONFLICT` e `UNREADABLE`.

Um campo pode corretamente apresentar `value: null`,
`status: NOT_DISCLOSED` e `confidence: 95`: o sistema possui forte evidência de
que o emissor ainda não divulgou a informação.

O schema é compartilhado por todos os tipos de evento. Assim, campos que não
são exigidos para o evento atual podem permanecer `UNKNOWN` com `confidence: 0` sem tornar o
documento inseguro. O roteamento considera os campos materiais para o tipo de
evento — por exemplo, valor por ação em dividendos e proporção em grupamentos —,
além dos conflitos e falhas de validação. Confiança abaixo de 75% em campo material
sempre exige revisão.

## Revisão humana e exceções

O roteamento é baseado em regras e risco. Alguns gatilhos materiais são:

- Tipo de evento desconhecido ou contraditório;
- Identificadores conflitantes com os golden records;
- Falha em regras temporais ou financeiras;
- Campo crítico ilegível ou com baixa confiança;
- Ativo que não pôde ser confirmado na base de referência.

Informações explicitamente pendentes são direcionadas para acompanhamento, em
vez de serem classificadas como falha de extração. As exceções são classificadas
como negócio, validação, revisão ou erro técnico.

## Auditabilidade

Cada campo material contém:

- Valor e status explícito;
- Origem no documento, referência, derivação ou origem desconhecida;
- Confiança percentual de 0 a 100;
- Página e trecho da evidência;
- Método de extração (`NATIVE_TEXT` ou `OCR`);
- Resultados das validações determinísticas.

Na mesa de controle do frontend, essas informações aparecem por campo, junto da
justificativa da confiança. O operador também vê a decisão operacional e seus
motivos, o registro canônico usado na validação, conflitos com valores esperado
e observado, tentativas de extração e evidências da classificação do evento.
Cada registro permite baixar seu JSON e consultar o PDF original; o lote permite
baixar e navegar pelo relatório curto de exceções. Assim, o dado pode ser
auditado diretamente pela trilha estruturada, mantendo o documento disponível
como apoio sem torná-lo necessário para cada conferência.

O backend confirma se a evidência fornecida pela LLM realmente aparece na
página normalizada citada. Trechos não suportados são descartados e o campo é
marcado como ambíguo, em vez de ser aceito silenciosamente.

## Testes

Execute os testes do backend:

```bash
cd c_backend
source .venv/bin/activate
python -m pytest
```

Os testes de documento, OCR, tools de PDF e pipeline usam os PDFs sintéticos do
case em `a_data/a_input`. Como esse diretório é ignorado pelo Git, restaure essas
fixtures antes de executar a suíte completa. Sem elas, é possível validar a
fronteira HTTP e o endpoint do visualizador separadamente:

```bash
python -m pytest tests/test_api.py
```

Gere o build do frontend:

```bash
cd b_frontend
npm run typecheck
npm run build
```

A suíte não depende de chamadas reais à LLM. O agente pode ser substituído por
um mock, e as regras determinísticas são testadas isoladamente.

## Trade-offs deliberados

- **Sem arquitetura multiagente autônoma:** a cascata possui etapas fixas e
  auditáveis. Os modelos podem escolher entre as function callings explicitamente
  fornecidas para o documento atual, mas não criam agentes, delegam tarefas nem
  alteram a ordem do pipeline. Isso reduz comportamento emergente e facilita a
  reprodução de uma decisão.
- **Function calling com escopo restrito:** o agente acessa golden records e o
  PDF somente por funções vinculadas pelo backend. Não recebe caminho arbitrário,
  shell, filesystem genérico ou MCP. A limitação reduz flexibilidade, mas também
  reduz superfície de ataque e uso de evidência fora do documento atual.
- **Sem vector database:** cada aviso é processado individualmente; não há um
  grande corpus que exija recuperação semântica.
- **Filesystem e PostgreSQL em paralelo:** os arquivos atendem diretamente ao
  entregável e facilitam inspeção; o JSONB acrescenta histórico e capacidade de
  consulta. O custo é exigir um terceiro serviço no ambiente local.
- **Sem fila de tarefas:** o processamento é síncrono no MVP. Uma fila passa a
  ser justificável com usuários concorrentes, jobs longos, retries ou necessidade
  de retomada. Ainda assim, a reserva única por SHA-256 impede duas execuções
  simultâneas do mesmo conteúdo entre instâncias da API.
- **Deduplicação por hash do conteúdo:** nomes diferentes não burlam o cache e a
  restrição única no PostgreSQL resolve a corrida entre uploads. O custo é que
  qualquer alteração de um byte produz uma nova identidade, mesmo quando o PDF
  parece visualmente igual; não foi adotada deduplicação perceptual por ela poder
  fundir documentos financeiros distintos.
- **Sem LangChain:** o SDK do provider e a orquestração explícita em Python
  mantêm o fluxo de controle visível.
- **Percentual não probabilístico:** os campos e o documento usam uma fórmula
  explícita de evidência, consenso e validação. O resultado não deve ser
  interpretado como probabilidade calibrada de acerto sem um dataset rotulado.
- **Sem retentativa automática ilimitada de LLM:** há duas passagens básicas e,
  quando algum check falha, uma passagem forte. Repetir indefinidamente elevaria custo e poderia
  mascarar ambiguidade real em vez de encaminhá-la para uma pessoa.
- **Sem confirmação de identidade por fuzzy matching:** similaridade textual
  pode sugerir um registro, mas somente identificadores financeiros o confirmam.
- **Checksum de CNPJ não bloqueante:** a base de referência é sintética e a
  maioria dos CNPJs fornecidos não possui dígitos verificadores válidos.
- **Sem autenticação e isolamento multiusuário:** o case é executado localmente.
  Expor o serviço externamente exigiria autenticação, autorização, criptografia,
  retenção e segregação de documentos.

## Possíveis evoluções

- Avaliar novos providers e calibrar a cascata com métricas reais de qualidade,
  custo e latência;
- Adicionar fila assíncrona e consultas operacionais sobre o histórico;
- Implementar autenticação, autorização e isolamento por cliente;
- Capturar correções do operador como feedback auditável;
- Construir datasets de regressão e painéis de qualidade da extração;
- Adotar object storage criptografado e políticas de retenção para produção;
- Ampliar a taxonomia de eventos e os pacotes de regras por mercado.

As justificativas arquiteturais estão registradas nas
[decisões arquiteturais](f_docs/b_architecture/architecture-decisions.md), e a direção
da interface está documentada em
[design do frontend](f_docs/b_architecture/frontend-design.md).
