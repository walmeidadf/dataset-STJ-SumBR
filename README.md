# STJ-SumBR

Dataset de sumarização jurídica construído a partir de acórdãos públicos do Superior Tribunal de Justiça do Brasil (STJ). Cada exemplo alinha o inteiro teor de um acórdão com a ementa oficial produzida pela Secretaria de Jurisprudência do STJ.

O dataset está publicado no HuggingFace: [walmeidadf/STJ-SumBR](https://huggingface.co/datasets/walmeidadf/STJ-SumBR)

## Por que o STJ?

Os espelhos de acórdãos do STJ são documentos estruturados que já contêm pares (inteiro teor → resumo anotado por especialista), com supervisão humana de alta qualidade, sem custo adicional de anotação — ideais para sumarização supervisionada.

A partir de 2025, alguns ministros adotaram uma estrutura de ementa em quatro seções (I–IV), o que permite múltiplos targets de sumarização no mesmo exemplo.

## Esquema

```python
{
  # Identificação
  "id":                   str,        # ex: "REsp 1234567"
  "numero_registro":      str,        # chave interna do STJ (12 dígitos)
  "turma":                str,        # ex: "TERCEIRA TURMA"
  "area_direito":         str,        # civil | penal | público | misto
  "sigla_classe":         str,        # ex: "REsp", "AgInt no AREsp"
  "data_julgamento":      str,        # ISO 8601: "2026-04-22"
  "relator":              str,

  # Input
  "documento":            str | None, # inteiro teor sem ementa (relatório + votos)

  # Targets
  "ementa":               str,        # resumo técnico-jurídico oficial
  "resumo_contexto":      str | None, # I. CASO EM EXAME
  "resumo_instituto":     str | None, # II. QUESTÃO EM DISCUSSÃO
  "resumo_fundamentacao": str | None, # III. RAZÕES DE DECIDIR
  "resumo_entendimento":  str | None, # IV. DISPOSITIVO

  # Flags e metadados
  "is_estruturada":       bool,
  "has_integra":          bool,
  "n_tokens_documento":   int | None,
  "legislacao_citada":    list[str],
  "jurisprudencia_citada": str | None,
  "data_publicacao":      str | None,
}
```

### Configurações

| Config | Descrição | Exemplos |
|---|---|---|
| `full` | Exemplos com inteiro teor disponível | ~61k |
| `ementa_only` | Todos os espelhos, incluindo sem íntegra | ~127k |

Splits estratificados por ano de julgamento: **80 / 10 / 10**.

### Cobertura

10 colegiados do STJ (6 turmas, 3 seções, Corte Especial), período 2022–2026.

| Turma / Seção | Área |
|---|---|
| 1ª e 2ª Turma, 1ª Seção | público |
| 3ª e 4ª Turma, 2ª Seção | civil |
| 5ª e 6ª Turma, 3ª Seção | penal |
| Corte Especial | misto |

## Como usar

```python
from datasets import load_dataset

# Com inteiro teor (input + ementa)
ds = load_dataset("walmeidadf/STJ-SumBR", "full")

# Só exemplos com resumo estruturado I-IV
ds_struct = ds["train"].filter(lambda x: x["is_estruturada"])

# Maior volume, só ementa como target
ds_ementa = load_dataset("walmeidadf/STJ-SumBR", "ementa_only")
```

## Reprodução

```bash
# 1. Instalar dependências (requer uv)
uv sync

# 2. Configurar variáveis de ambiente
cp .env.example .env
# editar .env: HF_TOKEN e HF_REPO_ID

# 3. Baixar dados brutos
./run_overnight.sh              # todas as fases em background
# ou por fase:
uv run python src/fetch.py --phase espelhos --workers 8
uv run python src/fetch.py --phase metadados --workers 8
uv run python src/fetch.py --phase zips --workers 4

# 4. Processar
uv run python src/parse.py
uv run python src/join.py
uv run python src/clean.py
uv run python src/export.py --upload
```

## Fonte dos dados

Dados disponibilizados publicamente pelo STJ em [dadosabertos.web.stj.jus.br](https://dadosabertos.web.stj.jus.br):

- **Espelhos de acórdãos**: JSONs mensais por turma/seção, via API CKAN
- **Íntegras**: ZIPs diários com TXTs de texto completo, via API CKAN

## Licença

- **Dados originais (STJ)**: uso livre com atribuição — CNJ Portaria 209/2019
- **Dataset compilado**: CC BY 4.0
- **Código**: MIT

Os acórdãos são documentos públicos. Nenhuma anonimização foi aplicada na v1.

## Citação

```bibtex
@dataset{stj-sumbr-2026,
  title     = {STJ-SumBR: Dataset de sumarização jurídica a partir de acórdãos do STJ},
  author    = {Almeida, Wesley},
  year      = {2026},
  publisher = {Hugging Face},
  url       = {https://huggingface.co/datasets/walmeidadf/STJ-SumBR},
  note      = {Dados originais: STJ Dados Abertos (dadosabertos.web.stj.jus.br),
               licença CNJ Portaria 209/2019}
}
```
