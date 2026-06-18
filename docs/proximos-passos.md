# Próximos Passos — STJ-SumBR

Documento de continuidade para sessões futuras. Atualizado após publicação v1 no HuggingFace.

---

## Estado atual (junho 2026)

### O que foi feito

- [x] Exploração da API CKAN do STJ Dados Abertos
- [x] 10 colegiados confirmados (6 turmas, 3 seções, Corte Especial)
- [x] Análise exploratória: 737 acórdãos, taxa de match 93,4%, mediana 4.176 tokens
- [x] Migração para uv (`pyproject.toml`)
- [x] `src/fetch.py` — download de espelhos, metadados e ZIPs
- [x] `src/parse.py` — normalização, detecção de ementa estruturada I-IV
- [x] `src/join.py` — cruzamento por `numeroRegistro`, extração de TXT, remoção de ementa
- [x] `src/clean.py` — limpeza de texto, filtros de qualidade, deduplicação
- [x] `src/export.py` — splits estratificados, dois configs, upload HF
- [x] `tests/test_parse.py` — 14 testes passando
- [x] `run_overnight.sh` — wrapper nohup para download em background
- [x] Dataset publicado em [walmeidadf/STJ-SumBR](https://huggingface.co/datasets/walmeidadf/STJ-SumBR)
- [x] Dataset card com YAML frontmatter correto (`data/full/*.parquet`)

### Números da v1

| Métrica | Valor |
|---|---|
| Acórdãos totais (`ementa_only`) | 126.959 |
| Com inteiro teor (`full`) | 61.173 |
| Com resumo estruturado I-IV | 20.221 (15,9%) |
| Colegiados | 10 |
| Período | 2022–2026 |
| Tokens/documento — mediana | 4.411 |
| Tokens/documento — máximo | 124.097 |

### Arquivos de dados locais (não versionados no git)

| Caminho | Descrição |
|---|---|
| `data/raw/espelhos/<turma>/*.json` | ~491 JSONs mensais, todas as turmas |
| `data/raw/integras_meta/*.json` | 1.231 JSONs diários de metadados |
| `data/raw/integras_txt/<data>/*.txt` | 61.257 TXTs extraídos dos ZIPs |
| `data/processed/espelhos_normalized.jsonl` | 134.965 espelhos normalizados |
| `data/processed/dataset_full.jsonl` | com íntegras joined |
| `data/processed/dataset_clean.jsonl` | 126.959 registros limpos |
| `data/processed/hf_dataset/` | Parquets por config/split |

---

## Bugs conhecidos / pendências técnicas

- [ ] **1 JSON corrompido**: `data/raw/espelhos/segunda-secao/20240229.json` — fevereiro de 2024 tem 29 dias (ano bissexto), mas o arquivo não parseia; pode ser dado inválido do STJ
- [ ] **Corte Especial com menos matches**: menor taxa de match por volume menor de íntegras no período coberto
- [ ] **Erros 520/522 pontuais**: alguns arquivos do STJ retornam erro de servidor; re-rodar `fetch.py` recupera a maioria (idempotente por design)
- [ ] **git config**: `user.name` e `user.email` não configurados globalmente — commits mostram aviso

---

## Próximas melhorias

### Qualidade dos dados
- [ ] Verificar se outras turmas adotaram estrutura I-IV além das detectadas (Daniela Teixeira, Humberto Martins)
- [ ] Parsear `jurisprudencia_citada` como lista estruturada (hoje é string livre)
- [ ] Investigar acórdãos com `n_tokens_documento` > 50k (possíveis problemas de extração)
- [ ] Adicionar campo `decisao` (dispositivo da sessão de votação) como metadado auxiliar

### Pipeline
- [ ] Retry com backoff exponencial no `fetch.py` para erros 520/522
- [ ] Suporte a S3 para armazenamento dos dados brutos (`--s3-bucket`)
- [ ] Script de atualização incremental (novos meses sem re-baixar tudo)

### Dataset
- [ ] Calcular baselines ROUGE com modelo T5-base em PT-BR
- [ ] Definir se incluir `n_tokens_ementa` no schema (calculado mas não exportado)
- [ ] Avaliar divisão por área do direito como sub-config adicional

---

## Fluxo completo (re-rodar após novos downloads)

```bash
uv run python src/parse.py
uv run python src/join.py
uv run python src/clean.py
uv run python src/export.py --upload
```
