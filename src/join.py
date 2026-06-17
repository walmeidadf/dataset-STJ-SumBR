#!/usr/bin/env python3
"""
STJ-SumBR — join espelhos normalizados ↔ íntegras.

Input:
  data/processed/espelhos_normalized.jsonl
  data/raw/integras_meta/*.json
  data/raw/integras_txt/<YYYYMMDD>/<SeqDocumento>.txt

Output:
  data/processed/dataset_full.jsonl

Uso:
  uv run python src/join.py
  uv run python src/join.py --espelhos data/processed/sample_parsed.jsonl \
                             --output   data/processed/sample_joined.jsonl
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
META_DIR = BASE_DIR / "data" / "raw" / "integras_meta"
TXT_DIR = BASE_DIR / "data" / "raw" / "integras_txt"

# Marcadores que delimitam o início da ementa no TXT
EMENTA_RE = re.compile(r'\nE\s*M\s*E\s*N\s*T\s*A\s*\n', re.IGNORECASE)

ENC = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    return len(ENC.encode(text))


def build_meta_index(meta_dir: Path) -> dict[str, tuple[str, str]]:
    """
    Lê todos os JSONs de metadados e indexa por numeroRegistro.
    Retorna: {numeroRegistro: (SeqDocumento, dataPublicacao_sem_hifens)}
    Mantém apenas acórdãos.
    """
    index: dict[str, tuple[str, str]] = {}
    files = sorted(meta_dir.glob("*.json"))
    log.info(f"Indexando {len(files)} arquivos de metadados…")
    for f in files:
        try:
            records = json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:
            log.warning(f"Erro ao ler {f.name}: {e}")
            continue
        for r in records:
            if r.get("tipoDocumento") != "ACÓRDÃO":
                continue
            nr  = (r.get("numeroRegistro") or "").strip()
            seq = str(r.get("SeqDocumento", "")).strip()
            pub = (r.get("dataPublicacao") or "").strip().replace("-", "")
            if nr and seq and pub:
                index[nr] = (seq, pub)
    log.info(f"Índice: {len(index):,} acórdãos")
    return index


def load_txt(seq: str, date_key: str, txt_dir: Path) -> str | None:
    """Carrega o TXT de uma íntegra. Retorna None se não encontrado."""
    path = txt_dir / date_key / f"{seq}.txt"
    if not path.exists():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except Exception as e:
        log.warning(f"Erro ao ler {path}: {e}")
        return None


def strip_ementa_from_txt(txt: str) -> str:
    """Remove a ementa do final do TXT (tudo a partir de EMENTA)."""
    m = EMENTA_RE.search(txt)
    if m:
        return txt[: m.start()].rstrip()
    return txt.rstrip()


def join_record(espelho: dict, index: dict, txt_dir: Path) -> dict:
    """Enriquece um registro de espelho com o inteiro teor."""
    nr = espelho.get("numero_registro", "")
    result = dict(espelho)

    if nr not in index:
        result["documento"] = None
        result["seq_documento"] = None
        result["data_publicacao"] = None
        result["has_integra"] = False
        result["n_tokens_documento"] = None
        return result

    seq, date_key = index[nr]
    result["seq_documento"]   = seq
    result["data_publicacao"] = f"{date_key[:4]}-{date_key[4:6]}-{date_key[6:8]}"

    raw_txt = load_txt(seq, date_key, txt_dir)
    if raw_txt is None:
        result["documento"] = None
        result["has_integra"] = False
        result["n_tokens_documento"] = None
    else:
        documento = strip_ementa_from_txt(raw_txt)
        result["documento"]          = documento
        result["has_integra"]        = True
        result["n_tokens_documento"] = count_tokens(documento)

    return result


def run(espelhos_path: Path, output: Path, meta_dir: Path, txt_dir: Path) -> None:
    index = build_meta_index(meta_dir)

    output.parent.mkdir(parents=True, exist_ok=True)

    total = with_integra = without_integra = 0
    token_sum = 0

    with (
        espelhos_path.open(encoding="utf-8") as inp,
        output.open("w", encoding="utf-8") as out,
    ):
        for line in inp:
            line = line.strip()
            if not line:
                continue
            espelho = json.loads(line)
            record  = join_record(espelho, index, txt_dir)
            out.write(json.dumps(record, ensure_ascii=False) + "\n")
            total += 1
            if record["has_integra"]:
                with_integra += 1
                token_sum += record["n_tokens_documento"] or 0
            else:
                without_integra += 1

    match_rate = 100 * with_integra / max(total, 1)
    avg_tokens = token_sum // max(with_integra, 1)
    log.info(
        f"Join concluído — {total:,} registros, "
        f"{with_integra:,} com íntegra ({match_rate:.1f}%), "
        f"{without_integra:,} sem íntegra"
    )
    log.info(f"Tokens médios por documento: {avg_tokens:,}")
    log.info(f"Output: {output}")


def main():
    parser = argparse.ArgumentParser(description="Join espelhos ↔ íntegras")
    parser.add_argument(
        "--espelhos",
        type=Path,
        default=PROCESSED_DIR / "espelhos_normalized.jsonl",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROCESSED_DIR / "dataset_full.jsonl",
    )
    parser.add_argument("--meta-dir", type=Path, default=META_DIR)
    parser.add_argument("--txt-dir",  type=Path, default=TXT_DIR)
    args = parser.parse_args()

    run(args.espelhos, args.output, args.meta_dir, args.txt_dir)


if __name__ == "__main__":
    main()
