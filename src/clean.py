#!/usr/bin/env python3
"""
STJ-SumBR — limpeza e filtros de qualidade.

Input:  data/processed/dataset_full.jsonl
Output: data/processed/dataset_clean.jsonl

Uso:
  uv run python src/clean.py
  uv run python src/clean.py --input data/processed/sample_joined.jsonl \
                              --output data/processed/sample_clean.jsonl
"""

import argparse
import json
import logging
import re
from pathlib import Path

import tiktoken

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
PROCESSED_DIR = BASE_DIR / "data" / "processed"

ENC = tiktoken.get_encoding("cl100k_base")

MIN_TOKENS_DOC    = 500
MIN_TOKENS_EMENTA = 50
MIN_TOKENS_RESUMO = 20   # por subcampo estruturado

# Substitui <br> e variações por newline
BR_RE = re.compile(r'<br\s*/?>', re.IGNORECASE)
# Colapsa 3+ newlines em 2
NEWLINES_RE = re.compile(r'\n{3,}')
# Colapsa espaços múltiplos numa linha
SPACES_RE = re.compile(r'[^\S\n]{2,}')


def clean_text(text: str | None) -> str | None:
    if not text:
        return text
    text = BR_RE.sub('\n', text)
    text = NEWLINES_RE.sub('\n\n', text)
    text = SPACES_RE.sub(' ', text)
    return text.strip()


def passes_quality(record: dict) -> tuple[bool, str]:
    """
    Verifica filtros de qualidade mínima.
    Retorna (passa, motivo_de_rejeicao).
    """
    ementa = record.get("ementa") or ""
    n_ementa = len(ENC.encode(ementa))
    if n_ementa < MIN_TOKENS_EMENTA:
        return False, f"ementa curta ({n_ementa} tokens)"

    if record.get("has_integra"):
        doc = record.get("documento") or ""
        n_doc = len(ENC.encode(doc))
        if n_doc < MIN_TOKENS_DOC:
            return False, f"documento curto ({n_doc} tokens)"

    if record.get("is_estruturada"):
        # resumo_entendimento é o dispositivo — naturalmente curto; não filtrar
        for field in ("resumo_contexto", "resumo_instituto", "resumo_fundamentacao"):
            val = record.get(field) or ""
            if val:
                n = len(ENC.encode(val))
                if n < MIN_TOKENS_RESUMO:
                    return False, f"{field} curto ({n} tokens)"

    return True, ""


def clean_record(record: dict) -> dict:
    r = dict(record)
    r["documento"] = clean_text(r.get("documento"))
    r["ementa"]    = clean_text(r.get("ementa"))
    for field in ("resumo_contexto", "resumo_instituto",
                  "resumo_fundamentacao", "resumo_entendimento"):
        r[field] = clean_text(r.get(field))
    # atualizar contagem de tokens após limpeza
    if r.get("documento"):
        r["n_tokens_documento"] = len(ENC.encode(r["documento"]))
    return r


def run(input_path: Path, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    seen_nr: set[str] = set()
    total = kept = deduped = rejected = 0
    reject_reasons: dict[str, int] = {}

    with (
        input_path.open(encoding="utf-8") as inp,
        output_path.open("w", encoding="utf-8") as out,
    ):
        for line in inp:
            line = line.strip()
            if not line:
                continue
            total += 1
            record = json.loads(line)

            # deduplicação por numero_registro
            nr = record.get("numero_registro", "")
            if nr and nr in seen_nr:
                deduped += 1
                continue
            if nr:
                seen_nr.add(nr)

            ok, reason = passes_quality(record)
            if not ok:
                rejected += 1
                reject_reasons[reason] = reject_reasons.get(reason, 0) + 1
                continue

            out.write(json.dumps(clean_record(record), ensure_ascii=False) + "\n")
            kept += 1

    log.info(
        f"Clean concluído — {total:,} entrada, "
        f"{kept:,} mantidos, "
        f"{deduped} duplicatas, "
        f"{rejected} rejeitados por qualidade"
    )
    if reject_reasons:
        for reason, count in sorted(reject_reasons.items(), key=lambda x: -x[1]):
            log.info(f"  rejeitados ({reason}): {count}")
    log.info(f"Output: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Limpeza e filtros de qualidade")
    parser.add_argument(
        "--input",
        type=Path,
        default=PROCESSED_DIR / "dataset_full.jsonl",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROCESSED_DIR / "dataset_clean.jsonl",
    )
    args = parser.parse_args()
    run(args.input, args.output)


if __name__ == "__main__":
    main()
