# AGENTS.md — Guia para ferramentas de IA

Este arquivo documenta o contexto técnico que ferramentas de IA precisam para trabalhar neste projeto de forma eficiente, sem precisar re-derivar decisões já tomadas.

## O que é este projeto

STJ-SumBR é um pipeline de coleta e processamento de dados jurídicos do STJ para gerar um dataset de sumarização no HuggingFace. O projeto consome dois conjuntos de dados públicos e os une em pares supervisionados (inteiro teor → resumo).

## Estrutura do projeto

```
stj-sumbr/
├── data/
│   ├── raw/
│   │   ├── espelhos/            # JSONs mensais por turma (1 arquivo = 1 mês, ~500–2000 registros)
│   │   ├── integras_meta/       # JSONs diários de metadados das íntegras
│   │   └── integras_zip/        # ZIPs diários com TXTs de texto completo
│   └── processed/               # dataset final (parquet ou jsonl)
├── src/
│   ├── fetch.py      # download de dados brutos
│   ├── parse.py      # extração e normalização de campos
│   ├── join.py       # join espelhos ↔ íntegras
│   ├── clean.py      # limpeza de texto e remoção de artefatos
│   └── export.py     # geração do dataset HuggingFace
├── tests/
│   └── test_parse.py
├── docs/
│   ├── proximos-passos.md
│   └── fase1-exploracao.md
├── .env              # HF_TOKEN (nunca commitar)
└── requirements.txt
```

## Fontes de dados

### 1. Espelhos de acórdãos (por turma)

- **API**: CKAN em `https://dadosabertos.web.stj.jus.br/api/3/action/package_show?id=<slug>`
- **Slugs disponíveis** (todos confirmados com 49–50 arquivos JSON cada):
  - `espelhos-de-acordaos-primeira-turma`
  - `espelhos-de-acordaos-segunda-turma`
  - `espelhos-de-acordaos-terceira-turma`
  - `espelhos-de-acordaos-quarta-turma`
  - `espelhos-de-acordaos-quinta-turma`
  - `espelhos-de-acordaos-sexta-turma`
  - `espelhos-de-acordaos-corte-especial`
  - `espelhos-de-acordaos-primeira-secao`
  - `espelhos-de-acordaos-segunda-secao`
  - `espelhos-de-acordaos-terceira-secao`
- **Formato**: Lista JSON de registros (um arquivo por mês, ex: `20260531.json`)
- **Campos relevantes**: ver seção "Mapeamento de campos" abaixo

### 2. Íntegras de decisões e acórdãos

- **Slug**: `integras-de-decisoes-terminativas-e-acordaos-do-diario-da-justica`
- **Metadados**: JSONs diários, nome `metadados<AAAAMMDD>.json`, lista de registros
- **Texto completo**: ZIPs diários, nome `<AAAAMMDD>.zip`, contém TXTs nomeados por `SeqDocumento`
- **Encoding**: UTF-8 tanto nos JSONs quanto nos TXTs dentro do ZIP
  - EXCEÇÃO: `dicionariointegrasdecisoes.csv` está em latin-1 (só o dicionário, não os dados)
- **Separador no texto completo**: `<br>` (HTML) para quebras de linha

## Mapeamento de campos — espelhos

| Campo no JSON | Campo no dataset | Tipo | Notas |
|---|---|---|---|
| `numeroProcesso` | `id` | str | ex: `"1970097"` — sem classe; usar `siglaClasse + " " + numeroProcesso` |
| `numeroRegistro` | `numero_registro` | str | 12 dígitos; **chave de join** com íntegras |
| `nomeOrgaoJulgador` | `turma` | str | ex: `"TERCEIRA TURMA"` |
| — | `area_direito` | str | derivado de `nomeOrgaoJulgador`; ver mapeamento abaixo |
| `siglaClasse` | `sigla_classe` | str | ex: `"REsp"`, `"AgInt no AREsp"` |
| `dataDecisao` | `data_julgamento` | str | formato `YYYYMMDD` → converter para ISO 8601 |
| `ministroRelator` | `relator` | str | |
| `ementa` | `ementa` | str | pode ser `None` em raros casos; filtrar |
| `jurisprudenciaCitada` | `jurisprudencia_citada` | str | string livre, não lista |
| `referenciasLegislativas` | `legislacao_citada` | list | lista de strings no formato `"LEG:FED LEI:010406 ANO:2002"` |

**Campos ausentes nos espelhos** (não existem no JSON real):
- `teseJuridica` → sempre `null` na Terceira Turma
- `termosAuxiliares` → sempre `null`
- `classePadronizada` → sempre `null`
- `numeroDocumento` → sempre `null`

**Campo `dataPublicacao`**: string suja, ex: `"DJEN       DATA:27/04/2026"`. Usar `dataDecisao` para estratificação por ano.

## Mapeamento de campos — íntegras metadados

| Campo no JSON | Uso | Notas |
|---|---|---|
| `SeqDocumento` | nome do TXT no ZIP | ex: `370905657` → `370905657.txt` |
| `numeroRegistro` | chave de join com espelhos | mesmo 12 dígitos |
| `tipoDocumento` | filtro | usar apenas `"ACÓRDÃO"` |
| `dataPublicacao` | ISO 8601 `"2026-04-27"` | para localizar o ZIP correto |
| `processo` | alternativa ao join | ex: `"REsp 1970097"` |

## Lógica de join (espelhos ↔ íntegras)

1. Indexar metadados por `numeroRegistro` → `{nr: (SeqDocumento, dataPublicacao)}`
2. Para cada espelho, buscar o `numeroRegistro` no índice
3. Se encontrado com `tipoDocumento == "ACÓRDÃO"`: marcar como `has_integra = True`
4. O ZIP do dia é `<dataPublicacao sem hífens>.zip` → ex: `20260427.zip`
5. O TXT é `<SeqDocumento>.txt` dentro do ZIP
6. **Taxa de match observada**: 93,4% (Terceira Turma, maio 2026)

## Estrutura do inteiro teor (TXT)

```
ACÓRDÃO
<dispositivo da sessão>
<texto do relatório>
É o relatório.
<texto do voto do relator>
<textos de votos concorrentes se houver>
EMENTA
<texto da ementa — DEVE SER REMOVIDO do campo `documento`>
```

**Atenção crítica**: o TXT termina com a ementa. Ao construir o campo `documento`, tudo a partir do marcador `\nEMENTA\n` deve ser removido para evitar vazamento do target.

## Parsing do resumo estruturado

A ementa pode conter até 4 seções em formato romano, introduzidas a partir de 2025 por 2 ministros (Daniela Teixeira: ~90%, Humberto Martins: ~40-65%):

```
I. CASO EM EXAME       → resumo_contexto
II. QUESTÃO EM DISCUSSÃO → resumo_instituto
III. RAZÕES DE DECIDIR  → resumo_fundamentacao
IV. DISPOSITIVO (E TESE) → resumo_entendimento
```

**Regex de detecção**:
```python
import re
SECTION_RE = re.compile(
    r'(?:^|\n)\s*(?:I{1,3}V?|VI?I{0,3})\.\s+'
    r'(CASO EM EXAME|QUESTÃO EM DISCUSSÃO|QUESTAO EM DISCUSSAO|'
    r'RAZÕES DE DECIDIR|RAZOES DE DECIDIR|DISPOSITIVO.*?TESE|DISPOSITIVO)',
    re.IGNORECASE
)
```

Exemplos de estrutura real encontrados nos dados:
- `I. Caso em exame` (minúsculo nos dados de 2025)
- `I. CASO EM EXAME` (maiúsculo nos de 2026)
- `IV. DISPOSITIVO E TESE` ou `IV. DISPOSITIVO`

## Mapeamento turma → area_direito

```python
AREA_MAP = {
    "PRIMEIRA TURMA":   "público",
    "SEGUNDA TURMA":    "público",
    "TERCEIRA TURMA":   "civil",
    "QUARTA TURMA":     "civil",
    "QUINTA TURMA":     "penal",
    "SEXTA TURMA":      "penal",
    "CORTE ESPECIAL":   "misto",
    "PRIMEIRA SEÇÃO":   "público",
    "SEGUNDA SEÇÃO":    "civil",
    "TERCEIRA SEÇÃO":   "penal",
}
```

## Variáveis de ambiente (.env)

```
HF_TOKEN=hf_...         # token do HuggingFace para upload
```

O download dos dados do STJ é público e não requer autenticação.

## Decisões de design já tomadas (não reverter sem justificativa)

1. **Todas as 9 turmas/seções na v1** — o mercado PT-BR está vazio; abrangência > restrição
2. **Íntegra real como `documento`** — sem íntegra não é dataset de sumarização
3. **`ementa_only` como config separada** — não descartar os ~7% sem íntegra
4. **Subcampos do resumo estruturado são opcionais** — só ~10-20% dos acórdãos de 2025+ os têm; flag `is_estruturada`
5. **Sem anonimização na v1** — acórdãos são documentos públicos; seguir precedente do RulingBR
6. **CC BY 4.0 + atribuição STJ** — compatível com CNJ Portaria 209/2019
7. **Split estratificado por `data_julgamento` (ano)** — 80/10/10

## Gotchas conhecidos

- `dic_integras.csv` está em latin-1, mas os JSONs de dados são UTF-8 limpo
- `dataPublicacao` dos espelhos é string livre, não ISO — usar `dataDecisao` (AAAAMMDD) para datas
- Os ZIPs diários contêm acórdãos de TODAS as turmas, não só da que está sendo processada — extrair seletivamente por `SeqDocumento`
- Alguns espelhos têm `ementa = null` (raro, <1%) — filtrar na etapa de limpeza
- O campo `id` nos espelhos é um código interno (`"956519"`), não o número do processo legível — construir o ID legível como `siglaClasse + " " + numeroProcesso`

## Escopo e volume estimado

- **Espelhos disponíveis**: ~49 arquivos × 9 turmas = ~441 arquivos JSON
- **Acórdãos totais estimados**: ~176.000
- **Com íntegra (~93%)**: ~163.700
- **Com resumo estruturado (~10-20% de 2025+)**: ~8.000–15.000
- **Download bruto de ZIPs**: ~17 GB (Terceira Turma) × ~9 = ~150 GB total
- **Storage após extração seletiva dos TXTs**: ~4 GB
- **Tokens médios por documento**: 4.176 (mediana, Terceira Turma)
