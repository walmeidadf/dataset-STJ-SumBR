# STJ-SumBR

Dataset de sumarização jurídica estruturada usando acórdãos públicos do Superior Tribunal de Justiça do Brasil.

## Visão geral

O STJ-SumBR é o primeiro dataset de sumarização jurídica em português brasileiro com cobertura de corte superior federal e múltiplos targets de sumarização. Cada exemplo alinha o inteiro teor de um acórdão (documento longo) com até cinco formas de resumo redigidas por juristas do próprio STJ.

### Por que o STJ?

Os espelhos de acórdãos do STJ são documentos estruturados produzidos pela Secretaria de Jurisprudência. Eles já contêm pares (inteiro teor → resumo anotado por especialista), com supervisão humana de altíssima qualidade, sem custo adicional de anotação. Isso os torna ideais para um dataset de sumarização supervisionada.

### Diferencial em relação ao que existe

| Dataset | Idioma | Tribunal | Docs | Targets | Em produção |
|---|---|---|---|---|---|
| RulingBR | PT-BR | STF | 10k | 1 (ementa) | Não (só em paper) |
| EUR-Lex-Sum (PT) | PT-EU | EU | ~800 | 1 | Sim |
| joelniklaus/brazilian_court_decisions | PT-BR | TJAL (estadual) | 4k | Classificação | Sim |
| **STJ-SumBR** | **PT-BR** | **STJ (federal)** | **~176k** | **5** | **Este projeto** |

## Esquema do dataset

```python
{
  # Identificação
  "id":                   str,   # ex: "REsp 1234567/SP"
  "numero_registro":      str,   # chave interna do STJ (12 dígitos)
  "turma":                str,   # ex: "TERCEIRA TURMA"
  "area_direito":         str,   # derivado da turma: civil, penal, público, etc.
  "sigla_classe":         str,   # ex: "REsp", "AgInt no AREsp"
  "data_julgamento":      str,   # ISO 8601: "2026-04-22"
  "relator":              str,   # nome do Ministro relator

  # Input da sumarização
  "documento":            str,   # inteiro teor (relatório + votos), ementa removida

  # Targets de sumarização
  "ementa":               str,   # Target 1 — resumo técnico-jurídico oficial
  "resumo_entendimento":  str | None,  # Target 2 — IV. DISPOSITIVO / como foi decidido
  "resumo_instituto":     str | None,  # Target 3 — II. QUESTÃO EM DISCUSSÃO / o que foi pedido
  "resumo_contexto":      str | None,  # Target 4 — I. CASO EM EXAME / os fatos
  "resumo_fundamentacao": str | None,  # Target 5 — III. RAZÕES DE DECIDIR / por que decidiu

  # Flag de qualidade
  "is_estruturada":       bool,  # True quando os 4 subcampos estão presentes

  # Metadados auxiliares
  "legislacao_citada":    list[str],  # ex: ["LEG:FED LEI:010406 ANO:2002"]
  "jurisprudencia_citada": list[str],
  "n_tokens_documento":   int,
  "n_tokens_ementa":      int,
}
```

### Splits

| Split | Proporção | Critério de estratificação |
|---|---|---|
| `train` | 80% | por ano de julgamento |
| `validation` | 10% | por ano de julgamento |
| `test` | 10% | por ano de julgamento |

### Configurações (configs)

- `full` — apenas exemplos com inteiro teor disponível (campo `documento` preenchido)
- `ementa_only` — todos os espelhos, inclusive os sem íntegra pareada

### Filtros de qualidade mínima

- `documento` ≥ 500 tokens
- `ementa` ≥ 50 tokens
- Cada `resumo_*` ≥ 20 tokens (quando `is_estruturada = True`)

## Turmas cobertas

| Turma | Área do direito |
|---|---|
| 1ª Turma | público |
| 2ª Turma | público |
| 3ª Turma | civil |
| 4ª Turma | civil |
| 5ª Turma | penal |
| 6ª Turma | penal |
| Corte Especial | misto |
| 1ª Seção | público |
| 2ª Seção | civil |
| 3ª Seção | penal |

## Como usar

```python
from datasets import load_dataset

# Dataset completo (com íntegra)
ds = load_dataset("seu-usuario/stj-sumbr", "full")

# Só exemplos com resumo estruturado (4 subcampos)
ds_struct = ds.filter(lambda x: x["is_estruturada"])

# Só ementa como target (maior volume)
ds_ementa = load_dataset("seu-usuario/stj-sumbr", "ementa_only")
```

## Reprodução

```bash
# 1. Instalar dependências
pip install -r requirements.txt

# 2. Configurar variáveis de ambiente
cp .env.example .env
# editar .env com HF_TOKEN

# 3. Baixar dados brutos (todas as turmas + íntegras)
python src/fetch.py --all --workers 8

# 4. Processar e gerar dataset
python src/parse.py
python src/join.py
python src/clean.py
python src/export.py
```

## Fonte dos dados

Os dados originais são disponibilizados pelo STJ em:
- **Espelhos de acórdãos**: `dadosabertos.web.stj.jus.br` — formato JSON, atualização mensal
- **Íntegras de acórdãos**: `dadosabertos.web.stj.jus.br` — texto completo em ZIP diário

## Licença

- **Dados originais**: CNJ Portaria 209/2019 — uso livre com atribuição ao STJ
- **Dataset compilado**: CC BY 4.0 — atribuição ao STJ e aos autores deste projeto
- **Código**: MIT

Os acórdãos do STJ são documentos públicos por natureza. Não foi aplicada anonimização na v1.

## Citação

```bibtex
@dataset{stj-sumbr-2026,
  title     = {STJ-SumBR: A Structured Legal Summarization Dataset for Brazilian Portuguese},
  author    = {},
  year      = {2026},
  publisher = {HuggingFace},
  url       = {https://huggingface.co/datasets/seu-usuario/stj-sumbr},
  note      = {Dados originais: STJ Dados Abertos, licença CNJ Portaria 209/2019}
}
```
