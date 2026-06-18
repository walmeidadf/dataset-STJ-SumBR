#!/usr/bin/env python3
"""
STJ-SumBR — geração do dataset HuggingFace.

Input:  data/processed/dataset_clean.jsonl
Output: data/processed/train.parquet, validation.parquet, test.parquet

Dois configs gerados:
  full        — registros com documento (has_integra=True)
  ementa_only — todos os registros (documento=None para os sem íntegra)

Uso:
  uv run python src/export.py
  uv run python src/export.py --input data/processed/sample_clean.jsonl \
                               --output-dir data/processed/sample_export
  uv run python src/export.py --upload  # faz upload para o HuggingFace Hub
"""

import argparse
import json
import logging
import os
from collections import Counter
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
PROCESSED_DIR = BASE_DIR / "data" / "processed"

SPLIT_RATIOS = {"train": 0.80, "validation": 0.10, "test": 0.10}

# Colunas presentes no dataset final
COLUMNS_FULL = [
    "id", "numero_registro", "sigla_classe", "turma", "area_direito",
    "data_julgamento", "relator", "ementa", "documento",
    "jurisprudencia_citada", "legislacao_citada",
    "resumo_contexto", "resumo_instituto", "resumo_fundamentacao",
    "resumo_entendimento", "is_estruturada",
    "has_integra", "seq_documento", "data_publicacao", "n_tokens_documento",
]


def stratified_split(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """
    Split 80/10/10 estratificado por ano de data_julgamento.
    Anos com < 10 registros vão inteiros para treino.
    """
    df = df.copy()
    df["_ano"] = df["data_julgamento"].str[:4].fillna("0000")

    train_idx, val_idx, test_idx = [], [], []
    for ano, group in df.groupby("_ano"):
        n = len(group)
        if n < 10:
            train_idx.extend(group.index.tolist())
            continue
        idx = group.sample(frac=1, random_state=42).index.tolist()
        n_val  = max(1, int(n * SPLIT_RATIOS["validation"]))
        n_test = max(1, int(n * SPLIT_RATIOS["test"]))
        test_idx.extend(idx[:n_test])
        val_idx.extend(idx[n_test: n_test + n_val])
        train_idx.extend(idx[n_test + n_val:])

    splits = {
        "train":      df.loc[train_idx],
        "validation": df.loc[val_idx],
        "test":       df.loc[test_idx],
    }
    return splits


def print_stats(df: pd.DataFrame, label: str) -> None:
    log.info(f"--- {label} ---")
    log.info(f"  Total: {len(df):,}")
    if "turma" in df.columns:
        by_turma = df["turma"].value_counts()
        for turma, count in by_turma.items():
            log.info(f"  {turma}: {count:,}")
    if "data_julgamento" in df.columns:
        by_ano = df["data_julgamento"].str[:4].value_counts().sort_index()
        log.info(f"  Anos: {dict(by_ano)}")
    if "is_estruturada" in df.columns:
        n_est = df["is_estruturada"].sum()
        log.info(f"  Estruturados: {n_est:,} ({100*n_est/max(len(df),1):.1f}%)")
    if "n_tokens_documento" in df.columns:
        tokens = df["n_tokens_documento"].dropna()
        if len(tokens):
            log.info(
                f"  Tokens documento — mediana: {int(tokens.median()):,}, "
                f"média: {int(tokens.mean()):,}, max: {int(tokens.max()):,}"
            )


def run(input_path: Path, output_dir: Path, upload: bool = False) -> None:
    with input_path.open(encoding="utf-8") as f:
        records = [json.loads(l) for l in f if l.strip()]
    df = pd.DataFrame(records)

    # Garantir colunas ausentes (dados parciais de amostra)
    for col in COLUMNS_FULL:
        if col not in df.columns:
            df[col] = None

    df = df[COLUMNS_FULL]

    log.info(f"Registros carregados: {len(df):,}")
    print_stats(df, "Dataset completo")

    # Config: full (com íntegra)
    df_full = df[df["has_integra"] == True].reset_index(drop=True)
    log.info(f"Config 'full': {len(df_full):,} registros")

    # Config: ementa_only (todos)
    df_ementa = df.copy()

    output_dir.mkdir(parents=True, exist_ok=True)

    for config_name, df_config in [("full", df_full), ("ementa_only", df_ementa)]:
        config_dir = output_dir / config_name
        config_dir.mkdir(exist_ok=True)
        splits = stratified_split(df_config)
        for split_name, split_df in splits.items():
            split_df = split_df.drop(columns=["_ano"], errors="ignore")
            out = config_dir / f"{split_name}.parquet"
            split_df.to_parquet(out, index=False, row_group_size=5_000)
            log.info(f"  {config_name}/{split_name}: {len(split_df):,} → {out.name}")

    # Estatísticas por split (config full)
    splits_full = stratified_split(df_full)
    for name, split_df in splits_full.items():
        print_stats(split_df.drop(columns=["_ano"], errors="ignore"), f"full/{name}")

    if upload:
        _upload_to_hub(output_dir)


def _upload_to_hub(output_dir: Path) -> None:
    load_dotenv(BASE_DIR / ".env")
    token = os.getenv("HF_TOKEN")
    if not token:
        log.error("HF_TOKEN não encontrado em .env")
        return

    try:
        from huggingface_hub import HfApi
    except ImportError:
        log.error("huggingface_hub não instalado")
        return

    api = HfApi(token=token)
    repo_id = os.getenv("HF_REPO_ID") or os.getenv("HF_REPO", "stj-sumbr")
    log.info(f"Upload para {repo_id}…")

    # Dataset card
    card_path = BASE_DIR / "dataset_card.md"
    if card_path.exists():
        api.upload_file(
            path_or_fileobj=str(card_path),
            path_in_repo="README.md",
            repo_id=repo_id,
            repo_type="dataset",
        )
        log.info("  Upload: README.md (dataset card)")

    for parquet in sorted(output_dir.rglob("*.parquet")):
        path_in_repo = str(parquet.relative_to(output_dir))
        api.upload_file(
            path_or_fileobj=str(parquet),
            path_in_repo=f"data/{path_in_repo}",
            repo_id=repo_id,
            repo_type="dataset",
        )
        log.info(f"  Upload: {path_in_repo}")

    log.info("Upload concluído.")


def main():
    parser = argparse.ArgumentParser(description="Gera splits e exporta para HuggingFace")
    parser.add_argument(
        "--input",
        type=Path,
        default=PROCESSED_DIR / "dataset_clean.jsonl",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROCESSED_DIR / "hf_dataset",
    )
    parser.add_argument(
        "--upload",
        action="store_true",
        help="Faz upload para o HuggingFace Hub após gerar os parquets",
    )
    args = parser.parse_args()
    run(args.input, args.output_dir, upload=args.upload)


if __name__ == "__main__":
    main()
