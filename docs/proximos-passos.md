# Próximos Passos — STJ-SumBR

Documento de continuidade para sessões futuras. Atualizado após a Fase 2 de desenvolvimento.

---

## Estado atual (junho 2026)

### O que foi feito

- [x] Exploração completa da API CKAN do STJ Dados Abertos
- [x] Confirmado: 9 turmas/seções com espelhos disponíveis (49–50 arquivos JSON mensais cada)
- [x] Confirmado: íntegras disponíveis em metadados JSON diários + ZIPs diários de texto completo
- [x] Análise de 737 acórdãos reais (Terceira Turma, maio 2026)
- [x] Taxa de match espelho↔íntegra: 93,4% por `numeroRegistro`
- [x] Token sizes: mediana 4.176 tokens/documento, 365 tokens/ementa
- [x] Descoberta: resumo estruturado (4 subcampos I-IV) só existe embutido na ementa, só em ~7-8% dos acórdãos de 2025+ na amostra (Daniela Teixeira ~90%, Humberto Martins ~40-65%)
- [x] Pesquisa de mercado HuggingFace: nenhum dataset de sumarização jurídica PT-BR existe no HF
- [x] Estrutura de projeto criada
- [x] Migração para uv (`pyproject.toml` substituindo `requirements.txt`)
- [x] `src/fetch.py` — download de dados brutos (todas as fases)
- [x] `src/parse.py` — normalização dos espelhos
- [x] `src/join.py` — join espelhos ↔ íntegras com extração de TXT e contagem de tokens
- [x] `src/clean.py` — limpeza de texto e filtros de qualidade
- [x] `src/export.py` — splits estratificados + upload HuggingFace
- [x] `tests/test_parse.py` — 14 testes passando
- [x] Pipeline end-to-end validado com amostra (737 espelhos + 28 íntegras do dia 20260427)
- [x] `run_overnight.sh` — script para rodar o download em background

### Decisões de arquitetura fixadas

1. Todas as 9 turmas na v1 (~176k acórdãos estimados)
2. Íntegra real como campo `documento`, com `ementa_only` como config separada
3. Campos `resumo_*` opcionais, flag `is_estruturada`; `resumo_entendimento` (dispositivo) não tem filtro de comprimento mínimo
4. Sem anonimização, CC BY 4.0
5. Split 80/10/10 estratificado por ano de `data_julgamento`
6. Join por `numeroRegistro` (12 dígitos)
7. Remover ementa do TXT antes de construir o campo `documento`
8. uv para gestão de pacotes e ambiente

### Dados de amostra disponíveis para testes

| Arquivo | Descrição |
|---|---|
| `data/raw/espelhos_20260531.json` | 737 espelhos (Terceira Turma, maio 2026) |
| `data/raw/integras_meta/*.json` | 37 dias de metadados (abr-mai 2026) |
| `data/raw/integras_txt/20260427/*.txt` | 28 TXTs extraídos do ZIP de 27/04/2026 |
| `data/processed/sample_parsed.jsonl` | 737 espelhos normalizados |
| `data/processed/sample_joined.jsonl` | 737 espelhos + 28 íntegras |
| `data/processed/sample_clean.jsonl` | 737 registros limpos |
| `data/processed/sample_export/` | Parquets de amostra (full + ementa_only) |

---

## Fase 2 — Download dos dados brutos (rodar overnight)

O script `src/fetch.py` tem 3 fases independentes.

```bash
# Executar overnight
./run_overnight.sh          # roda --all --workers 8

# Ou fase por fase
./run_overnight.sh --phase espelhos   # (~400 MB, rápido, valida API)
./run_overnight.sh --phase metadados  # (~1.2 GB)
./run_overnight.sh --phase zips       # (~150 GB bruto → ~4 GB pós-extração)

# Acompanhar progresso
tail -f logs/fetch_*.log

# Parar se necessário
kill $(cat logs/fetch.pid)
```

**Nota de disco**: o script já apaga cada ZIP após extrair os TXTs. Pico de uso simultâneo estimado em ~10–20 GB (workers=4 × ZIP máximo). Os 104 GB disponíveis são suficientes.

---

## Fase 3 — Parse e normalização (`src/parse.py`) ✅ PRONTO

```bash
uv run python src/parse.py
# → data/processed/espelhos_normalized.jsonl
```

---

## Fase 4 — Join espelhos ↔ íntegras (`src/join.py`) ✅ PRONTO

```bash
uv run python src/join.py
# → data/processed/dataset_full.jsonl
```

---

## Fase 5 — Limpeza (`src/clean.py`) ✅ PRONTO

```bash
uv run python src/clean.py
# → data/processed/dataset_clean.jsonl
```

---

## Fase 6 — Export para HuggingFace (`src/export.py`) ✅ PRONTO

```bash
uv run python src/export.py
# → data/processed/hf_dataset/{full,ementa_only}/{train,validation,test}.parquet

# Com upload (requer HF_TOKEN no .env)
uv run python src/export.py --upload
```

---

## Fase 7 — Dataset Card

A criar como `dataset_card.md`.

Seções obrigatórias para HuggingFace:
- Dataset Summary
- Supported Tasks
- Languages
- Dataset Structure (fields, splits, configs)
- Source Data (STJ Dados Abertos, licença)
- Considerations for Using the Data (dados públicos, sem anonimização)
- Citation
- Baseline ROUGE scores (t5-base ou similar)

---

## Fase 8 — Publicação no HuggingFace

```bash
# Definir namespace no .env
echo "HF_REPO=seu-usuario/stj-sumbr" >> .env
echo "HF_TOKEN=hf_..." >> .env

uv run python src/export.py --upload
```

---

## Questões em aberto para sessões futuras

- [ ] Verificar se outras turmas também têm ementas estruturadas (I-IV) ou é específico da 3ª Turma
- [ ] Definir o namespace HuggingFace (`seu-usuario/stj-sumbr`)
- [ ] Calcular baselines ROUGE com modelo T5-base em PT-BR
- [ ] Avaliar se `jurisprudencia_citada` (string livre com `<<REsp 123>>`) vale parsear como lista
- [ ] Verificar se a Corte Especial tem ementas estruturadas
- [ ] Definir se incluir `decisao` (dispositivo da sessão de votação) como campo auxiliar
- [ ] Configurar S3 para armazenamento dos dados brutos (alternativa ao local)
- [ ] Escrever Dataset Card

## Fluxo completo após o download

```bash
uv run python src/parse.py   # espelhos → normalized.jsonl
uv run python src/join.py    # + íntegras → full.jsonl
uv run python src/clean.py   # filtros → clean.jsonl
uv run python src/export.py  # → parquets + stats
```
