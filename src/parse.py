#!/usr/bin/env python3
"""
STJ-SumBR — parse e normalização dos espelhos de acórdãos.

Input:  data/raw/espelhos/**/*.json
Output: data/processed/espelhos_normalized.jsonl

Uso:
  uv run python src/parse.py
  uv run python src/parse.py --input data/raw/espelhos_20260531.json --output data/processed/sample.jsonl
"""

import argparse
import json
import logging
import re
from datetime import date
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"
PROCESSED_DIR = BASE_DIR / "data" / "processed"

AREA_MAP = {
    "PRIMEIRA TURMA":  "público",
    "SEGUNDA TURMA":   "público",
    "TERCEIRA TURMA":  "civil",
    "QUARTA TURMA":    "civil",
    "QUINTA TURMA":    "penal",
    "SEXTA TURMA":     "penal",
    "CORTE ESPECIAL":  "misto",
    "PRIMEIRA SEÇÃO":  "público",
    "SEGUNDA SEÇÃO":   "civil",
    "TERCEIRA SEÇÃO":  "penal",
}

# Detecta marcadores estruturais I–IV na ementa
SECTION_RE = re.compile(
    r'(?:^|\n)\s*(I{1,3}V?|VI?I{0,3})\.\s+'
    r'(CASO EM EXAME|QUESTÃO EM DISCUSSÃO|QUESTAO EM DISCUSSAO|'
    r'RAZÕES DE DECIDIR|RAZOES DE DECIDIR|DISPOSITIVO(?:.*?TESE)?|DISPOSITIVO)',
    re.IGNORECASE,
)

SECTION_LABELS = {
    "caso em exame":           "resumo_contexto",
    "questão em discussão":    "resumo_instituto",
    "questao em discussao":    "resumo_instituto",
    "razões de decidir":       "resumo_fundamentacao",
    "razoes de decidir":       "resumo_fundamentacao",
}


def _date_yyyymmdd_to_iso(value: str | None) -> str | None:
    if not value or len(value) < 8:
        return None
    try:
        return date(int(value[:4]), int(value[4:6]), int(value[6:8])).isoformat()
    except ValueError:
        return None


def _area_direito(orgao: str | None) -> str | None:
    if not orgao:
        return None
    key = orgao.strip().upper()
    # remove sufixo de número ordinal escrito por extenso se vier com acento
    key = re.sub(r'\s+DO\s+STJ$', '', key)
    return AREA_MAP.get(key)


def _parse_ementa_estruturada(ementa: str) -> dict:
    """
    Tenta extrair subcampos I-IV de uma ementa.
    Retorna dict com chaves resumo_* + is_estruturada.
    """
    result = {
        "resumo_contexto":       None,
        "resumo_instituto":      None,
        "resumo_fundamentacao":  None,
        "resumo_entendimento":   None,
        "is_estruturada":        False,
    }

    matches = list(SECTION_RE.finditer(ementa))
    if len(matches) < 2:
        return result

    result["is_estruturada"] = True
    for i, m in enumerate(matches):
        label_raw = m.group(2).lower().rstrip()
        # tudo até o próximo marcador (ou fim da string)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(ementa)
        text = ementa[start:end].strip()

        # mapear por prefixo — "dispositivo e tese" e variantes caem em resumo_entendimento
        field = SECTION_LABELS.get(label_raw)
        if field is None and label_raw.startswith("dispositivo"):
            field = "resumo_entendimento"

        if field:
            result[field] = text or None

    return result


def normalize_record(raw: dict) -> dict | None:
    """
    Converte um registro bruto de espelho no formato normalizado do dataset.
    Retorna None se o registro deve ser descartado.
    """
    ementa = raw.get("ementa")
    if not ementa:
        return None

    numero_processo = (raw.get("numeroProcesso") or "").strip()
    sigla_classe    = (raw.get("siglaClasse") or "").strip()
    numero_registro = (raw.get("numeroRegistro") or "").strip()
    orgao           = (raw.get("nomeOrgaoJulgador") or "").strip()
    data_decisao    = (raw.get("dataDecisao") or "").strip()
    relator         = (raw.get("ministroRelator") or "").strip()

    id_ = f"{sigla_classe} {numero_processo}".strip() if sigla_classe else numero_processo

    refs = raw.get("referenciasLegislativas")
    if isinstance(refs, str):
        refs = [refs] if refs else []
    elif not isinstance(refs, list):
        refs = []

    record = {
        "id":                id_,
        "numero_registro":   numero_registro,
        "sigla_classe":      sigla_classe or None,
        "turma":             orgao or None,
        "area_direito":      _area_direito(orgao),
        "data_julgamento":   _date_yyyymmdd_to_iso(data_decisao),
        "relator":           relator or None,
        "ementa":            ementa.strip(),
        "jurisprudencia_citada": (raw.get("jurisprudenciaCitada") or "").strip() or None,
        "legislacao_citada": refs,
    }

    estruturada = _parse_ementa_estruturada(ementa)
    record.update(estruturada)

    return record


def parse_file(path: Path) -> tuple[list[dict], int, int]:
    """Processa um arquivo JSON de espelhos. Retorna (records, total, descartados)."""
    try:
        raw_list = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        log.warning(f"Erro ao ler {path}: {e}")
        return [], 0, 0

    if not isinstance(raw_list, list):
        log.warning(f"{path}: esperava lista, encontrou {type(raw_list)}")
        return [], 0, 0

    records, discarded = [], 0
    for raw in raw_list:
        r = normalize_record(raw)
        if r is None:
            discarded += 1
        else:
            records.append(r)

    return records, len(raw_list), discarded


def run(inputs: list[Path], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)

    total_records = total_discarded = 0
    structured_count = 0

    with output.open("w", encoding="utf-8") as out:
        for path in inputs:
            records, total, discarded = parse_file(path)
            for r in records:
                out.write(json.dumps(r, ensure_ascii=False) + "\n")
            total_records += len(records)
            total_discarded += discarded
            structured_count += sum(1 for r in records if r.get("is_estruturada"))

    log.info(
        f"Parse concluído — {total_records:,} registros, "
        f"{total_discarded} descartados (ementa nula), "
        f"{structured_count} com estrutura I-IV "
        f"({100*structured_count/max(total_records,1):.1f}%)"
    )
    log.info(f"Output: {output}")


def main():
    parser = argparse.ArgumentParser(description="Parse espelhos → JSONL normalizado")
    parser.add_argument(
        "--input",
        nargs="+",
        type=Path,
        help="Arquivo(s) JSON de espelhos (default: data/raw/espelhos/**/*.json)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROCESSED_DIR / "espelhos_normalized.jsonl",
    )
    args = parser.parse_args()

    if args.input:
        inputs = args.input
    else:
        inputs = sorted((RAW_DIR / "espelhos").rglob("*.json"))
        if not inputs:
            # fallback: arquivos avulsos na raiz de raw (ex: espelhos_20260531.json)
            inputs = sorted(RAW_DIR.glob("espelhos_*.json"))

    if not inputs:
        log.error("Nenhum arquivo de espelhos encontrado.")
        return

    log.info(f"Processando {len(inputs)} arquivo(s)…")
    run(inputs, args.output)


if __name__ == "__main__":
    main()
