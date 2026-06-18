---
language:
  - pt
license: cc-by-4.0
task_categories:
  - summarization
task_ids:
  - news-articles-summarization
pretty_name: STJ-SumBR
size_categories:
  - 10K<n<100K
tags:
  - legal
  - portuguese
  - brazil
  - summarization
  - court-decisions
configs:
  - config_name: full
    data_files:
      - split: train
        path: full/train.parquet
      - split: validation
        path: full/validation.parquet
      - split: test
        path: full/test.parquet
  - config_name: ementa_only
    data_files:
      - split: train
        path: ementa_only/train.parquet
      - split: validation
        path: ementa_only/validation.parquet
      - split: test
        path: ementa_only/test.parquet
---

# STJ-SumBR

Dataset de sumarização jurídica construído a partir de acórdãos públicos do Superior Tribunal de Justiça do Brasil (STJ). Cada exemplo alinha o inteiro teor de um acórdão com a ementa oficial produzida pela Secretaria de Jurisprudência do STJ.

## Resumo

O STJ disponibiliza publicamente dois conjuntos de dados via [STJ Dados Abertos](https://dadosabertos.web.stj.jus.br): os **espelhos de acórdãos** (metadados estruturados e ementa) e as **íntegras** (texto completo em PDF convertido para TXT). Este projeto cruza essas duas fontes por `numeroRegistro` para produzir pares supervisionados adequados a tarefas de sumarização automática de decisões judiciais em português brasileiro.

A cobertura inclui as 10 colegiados do STJ (seis turmas, três seções e a Corte Especial), com acórdãos de 2022 a 2026.

## Tarefas suportadas

- **Sumarização extrativa/abstrativa** (`documento` → `ementa`)
- **Sumarização estruturada** (`documento` → `resumo_contexto`, `resumo_instituto`, `resumo_fundamentacao`, `resumo_entendimento`) — disponível em ~16% dos exemplos, produzidos por ministros que adotam a estrutura I-IV a partir de 2025

## Idioma

Português brasileiro (`pt-BR`). Linguagem jurídica formal.

## Estrutura do dataset

### Configurações

| Config | Descrição | Exemplos (aprox.) |
|---|---|---|
| `full` | Exemplos com inteiro teor disponível | ~57k |
| `ementa_only` | Todos os espelhos, incluindo os sem íntegra | ~127k |

### Splits

Estratificados por ano de julgamento (80 / 10 / 10).

### Campos

| Campo | Tipo | Descrição |
|---|---|---|
| `id` | `str` | Número do processo legível (`siglaClasse + numeroProcesso`) |
| `numero_registro` | `str` | Identificador interno do STJ (12 dígitos) |
| `turma` | `str` | Órgão julgador (ex: `"TERCEIRA TURMA"`) |
| `area_direito` | `str` | Área derivada da turma: `civil`, `penal`, `público`, `misto` |
| `sigla_classe` | `str` | Classe processual (ex: `"REsp"`, `"AgInt no AREsp"`) |
| `data_julgamento` | `str` | Data em ISO 8601 |
| `relator` | `str` | Ministro relator |
| `documento` | `str\|null` | Inteiro teor sem a ementa (relatório + votos). `null` nos exemplos sem íntegra |
| `ementa` | `str` | Ementa oficial — target principal de sumarização |
| `resumo_contexto` | `str\|null` | I. CASO EM EXAME — fatos do caso |
| `resumo_instituto` | `str\|null` | II. QUESTÃO EM DISCUSSÃO — questão jurídica central |
| `resumo_fundamentacao` | `str\|null` | III. RAZÕES DE DECIDIR — fundamentos |
| `resumo_entendimento` | `str\|null` | IV. DISPOSITIVO — resultado do julgamento |
| `is_estruturada` | `bool` | `True` quando os subcampos I-IV estão presentes |
| `legislacao_citada` | `list[str]` | Referências legislativas no formato STJ |
| `jurisprudencia_citada` | `str\|null` | Citações jurisprudenciais (campo livre) |
| `n_tokens_documento` | `int\|null` | Contagem de tokens (`tiktoken cl100k_base`) |
| `has_integra` | `bool` | Se o inteiro teor está disponível |
| `seq_documento` | `str\|null` | Identificador do TXT na fonte |
| `data_publicacao` | `str\|null` | Data de publicação no DJe (ISO 8601) |

### Exemplo

```python
{
  "id": "REsp 2027136",
  "turma": "TERCEIRA TURMA",
  "area_direito": "civil",
  "data_julgamento": "2024-08-27",
  "relator": "NANCY ANDRIGHI",
  "ementa": "DIREITO CIVIL. RECURSO ESPECIAL. RESPONSABILIDADE CIVIL...",
  "documento": "ACÓRDÃO\nVistos, relatados e discutidos estes autos...",
  "is_estruturada": False,
  "n_tokens_documento": 4391
}
```

## Estatísticas

| Métrica | Valor |
|---|---|
| Acórdãos totais (ementa_only) | ~127k |
| Com inteiro teor (full) | ~57k |
| Com resumo estruturado I-IV | ~20k (15,9%) |
| Turmas / seções cobertas | 10 |
| Período | 2022–2026 |
| Tokens por documento — mediana | 4.391 |
| Tokens por documento — máximo | ~124k |
| Tokens por ementa — mediana | ~365 |

## Dados originais

Os dados são disponibilizados publicamente pelo STJ em [dadosabertos.web.stj.jus.br](https://dadosabertos.web.stj.jus.br) sob a Portaria CNJ 209/2019, que permite uso livre com atribuição.

- **Espelhos de acórdãos**: JSONs mensais por turma/seção, via API CKAN
- **Íntegras**: ZIPs diários de TXTs, via API CKAN

O código de coleta e processamento está disponível em [github.com/walmeidadf/dataset-STJ-SumBR](https://github.com/walmeidadf/dataset-STJ-SumBR).

## Considerações de uso

- Os acórdãos são documentos públicos que podem conter nomes de partes, advogados e outros dados pessoais. Nenhuma anonimização foi aplicada, seguindo o mesmo princípio de datasets jurídicos publicados na literatura (ex: RulingBR).
- O campo `documento` pode ser longo (mediana ~4k tokens). Verifique os limites de contexto do modelo antes de usar.
- A taxa de match espelho↔íntegra varia por turma e período (~93% na Terceira Turma, maio 2026). Exemplos sem íntegra têm `documento = null` e `has_integra = false`.
- A estrutura I-IV está presente em acórdãos de 2025+ de ministros específicos. Não é representativa de toda a coleção.

## Licença

- **Dados originais (STJ)**: uso livre com atribuição — CNJ Portaria 209/2019
- **Dataset compilado**: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)
- **Código**: MIT

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
