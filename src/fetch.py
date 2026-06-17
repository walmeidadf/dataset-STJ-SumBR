#!/usr/bin/env python3
"""
STJ-SumBR — coleta de dados brutos.

Três fases independentes:
  Phase 1 (espelhos):  baixa os JSONs mensais de todas as turmas
  Phase 2 (metadados): baixa os JSONs diários de metadados das íntegras
  Phase 3 (zips):      a partir do cruzamento espelhos×metadados, baixa e
                       extrai apenas os TXTs necessários dos ZIPs diários

Uso:
  python src/fetch.py --phase espelhos  [--workers 8]
  python src/fetch.py --phase metadados [--workers 8]
  python src/fetch.py --phase zips      [--workers 4]
  python src/fetch.py --all             [--workers 8]
  python src/fetch.py --dry-run --all   # mostra o que seria baixado
"""

import argparse
import json
import logging
import os
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from tqdm import tqdm

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"
ESPELHOS_DIR = RAW_DIR / "espelhos"
META_DIR = RAW_DIR / "integras_meta"
ZIP_DIR = RAW_DIR / "integras_zip"
TXT_DIR = RAW_DIR / "integras_txt"

CKAN_API = "https://dadosabertos.web.stj.jus.br/api/3/action/package_show?id={}"

TURMA_SLUGS = [
    "espelhos-de-acordaos-primeira-turma",
    "espelhos-de-acordaos-segunda-turma",
    "espelhos-de-acordaos-terceira-turma",
    "espelhos-de-acordaos-quarta-turma",
    "espelhos-de-acordaos-quinta-turma",
    "espelhos-de-acordaos-sexta-turma",
    "espelhos-de-acordaos-corte-especial",
    "espelhos-de-acordaos-primeira-secao",
    "espelhos-de-acordaos-segunda-secao",
    "espelhos-de-acordaos-terceira-secao",
]

INTEGRAS_SLUG = (
    "integras-de-decisoes-terminativas-e-acordaos-do-diario-da-justica"
)

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "stj-sumbr/1.0 (research dataset)"})

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fetch_ckan_resources(slug: str) -> list[dict]:
    """Retorna a lista de resources de um pacote CKAN."""
    url = CKAN_API.format(slug)
    r = SESSION.get(url, timeout=30)
    r.raise_for_status()
    data = r.json()
    if not data.get("success"):
        raise ValueError(f"CKAN falhou para {slug}: {data.get('error')}")
    return data["result"]["resources"]


def download_file(url: str, dest: Path, dry_run: bool = False) -> bool:
    """Baixa url → dest. Pula se dest já existe. Retorna True se baixou."""
    if dest.exists():
        return False
    if dry_run:
        log.info(f"[DRY-RUN] {dest.name}  <-  {url}")
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    try:
        with SESSION.get(url, timeout=120, stream=True) as r:
            r.raise_for_status()
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(chunk_size=65536):
                    f.write(chunk)
        tmp.rename(dest)
        return True
    except Exception as exc:
        log.warning(f"Erro ao baixar {url}: {exc}")
        if tmp.exists():
            tmp.unlink()
        return False


def parallel_download(
    tasks: list[tuple[str, Path]],
    workers: int,
    dry_run: bool,
    desc: str,
) -> tuple[int, int]:
    """Executa downloads em paralelo. Retorna (baixados, pulados)."""
    downloaded = skipped = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(download_file, url, dest, dry_run): (url, dest)
            for url, dest in tasks
        }
        with tqdm(total=len(tasks), desc=desc, unit="file") as bar:
            for fut in as_completed(futures):
                try:
                    got = fut.result()
                    if got:
                        downloaded += 1
                    else:
                        skipped += 1
                except Exception as exc:
                    url, dest = futures[fut]
                    log.warning(f"Falha em {dest.name}: {exc}")
                    skipped += 1
                bar.update(1)
    return downloaded, skipped


# ---------------------------------------------------------------------------
# Phase 1 — Espelhos
# ---------------------------------------------------------------------------

def build_espelhos_tasks() -> list[tuple[str, Path]]:
    tasks = []
    for slug in TURMA_SLUGS:
        turma_name = slug.replace("espelhos-de-acordaos-", "")
        turma_dir = ESPELHOS_DIR / turma_name
        log.info(f"Consultando CKAN: {slug}")
        try:
            resources = fetch_ckan_resources(slug)
        except Exception as e:
            log.error(f"Erro ao consultar {slug}: {e}")
            continue
        jsons = [r for r in resources if r.get("format", "").upper() == "JSON"]
        for r in jsons:
            dest = turma_dir / r["name"]
            tasks.append((r["url"], dest))
        log.info(f"  {turma_name}: {len(jsons)} arquivos JSON")
    return tasks


def phase_espelhos(workers: int, dry_run: bool) -> None:
    log.info("=== Phase 1: Espelhos ===")
    tasks = build_espelhos_tasks()
    log.info(f"Total: {len(tasks)} arquivos JSON de espelhos")
    dl, sk = parallel_download(tasks, workers, dry_run, "Espelhos")
    log.info(f"Espelhos — baixados: {dl}, já existentes: {sk}")


# ---------------------------------------------------------------------------
# Phase 2 — Metadados das íntegras
# ---------------------------------------------------------------------------

def build_metadados_tasks() -> list[tuple[str, Path]]:
    log.info(f"Consultando CKAN: {INTEGRAS_SLUG}")
    resources = fetch_ckan_resources(INTEGRAS_SLUG)
    jsons = [r for r in resources if r.get("format", "").upper() == "JSON"]
    tasks = []
    for r in jsons:
        # nome: "metadados20260427" → arquivo: metadados20260427.json
        fname = r["name"] if r["name"].endswith(".json") else r["name"] + ".json"
        dest = META_DIR / fname
        tasks.append((r["url"], dest))
    log.info(f"Integras metadados: {len(tasks)} arquivos JSON diários")
    return tasks


def phase_metadados(workers: int, dry_run: bool) -> None:
    log.info("=== Phase 2: Metadados das íntegras ===")
    tasks = build_metadados_tasks()
    dl, sk = parallel_download(tasks, workers, dry_run, "Metadados")
    log.info(f"Metadados — baixados: {dl}, já existentes: {sk}")


# ---------------------------------------------------------------------------
# Phase 3 — ZIPs seletivos + extração de TXTs
# ---------------------------------------------------------------------------

def build_match_index() -> dict[str, tuple[str, str]]:
    """
    Lê todos os metadados de íntegras e indexa por numeroRegistro.
    Retorna: {numeroRegistro: (SeqDocumento, dataPublicacao)}
    Mantém apenas acórdãos (tipoDocumento == "ACÓRDÃO").
    """
    index: dict[str, tuple[str, str]] = {}
    meta_files = sorted(META_DIR.glob("*.json"))
    log.info(f"Construindo índice a partir de {len(meta_files)} arquivos de metadados…")
    for fpath in tqdm(meta_files, desc="Indexando metadados", unit="file"):
        try:
            records = json.loads(fpath.read_text(encoding="utf-8"))
        except Exception:
            continue
        for r in records:
            if r.get("tipoDocumento") != "ACÓRDÃO":
                continue
            nr = (r.get("numeroRegistro") or "").strip()
            seq = str(r.get("SeqDocumento", ""))
            pub = (r.get("dataPublicacao") or "").strip()
            if nr and seq and pub:
                index[nr] = (seq, pub)
    log.info(f"Índice: {len(index):,} acórdãos indexados")
    return index


def collect_needed_zips(index: dict) -> dict[str, list[str]]:
    """
    Percorre todos os espelhos baixados e descobre quais ZIPs e TXTs são necessários.
    Retorna: {data_yyyymmdd: [SeqDocumento, ...]}
    """
    needed: dict[str, list[str]] = {}
    espelhos_files = list(ESPELHOS_DIR.rglob("*.json"))
    log.info(f"Varrendo {len(espelhos_files)} arquivos de espelhos para encontrar matches…")
    matched = unmatched = 0
    for fpath in tqdm(espelhos_files, desc="Matching", unit="file"):
        try:
            records = json.loads(fpath.read_text(encoding="utf-8"))
        except Exception:
            continue
        for r in records:
            if r.get("tipoDeDecisao") != "ACÓRDÃO":
                continue
            nr = (r.get("numeroRegistro") or "").strip()
            if nr in index:
                seq, pub = index[nr]
                date_key = pub.replace("-", "")  # "2026-04-27" → "20260427"
                needed.setdefault(date_key, []).append(seq)
                matched += 1
            else:
                unmatched += 1
    log.info(
        f"Match: {matched:,} com íntegra, {unmatched:,} sem. "
        f"ZIPs necessários: {len(needed)}"
    )
    return needed


def fetch_integras_resources() -> dict[str, str]:
    """Retorna {data_yyyymmdd: url_zip} para todos os ZIPs das íntegras."""
    resources = fetch_ckan_resources(INTEGRAS_SLUG)
    zips = {}
    for r in resources:
        if r.get("format", "").upper() == "ZIP":
            name = r["name"]  # ex: "20260427.zip"
            date_key = name.replace(".zip", "")
            zips[date_key] = r["url"]
    return zips


def extract_txts_from_zip(zip_path: Path, seqs: list[str], out_dir: Path) -> int:
    """Extrai apenas os TXTs listados de um ZIP. Retorna quantos foram extraídos."""
    out_dir.mkdir(parents=True, exist_ok=True)
    seq_set = {f"{s}.txt" for s in seqs}
    extracted = 0
    try:
        with zipfile.ZipFile(zip_path) as zf:
            for name in zf.namelist():
                if name in seq_set:
                    dest = out_dir / name
                    if not dest.exists():
                        dest.write_bytes(zf.read(name))
                        extracted += 1
    except Exception as e:
        log.warning(f"Erro ao extrair {zip_path.name}: {e}")
    return extracted


def phase_zips(workers: int, dry_run: bool) -> None:
    log.info("=== Phase 3: ZIPs seletivos ===")

    # Construir índice e descobrir o que é necessário
    index = build_match_index()
    needed = collect_needed_zips(index)

    if not needed:
        log.warning("Nenhum match encontrado — execute as phases 1 e 2 primeiro.")
        return

    # Buscar URLs dos ZIPs
    log.info("Buscando URLs dos ZIPs no CKAN…")
    zip_urls = fetch_integras_resources()

    # Montar tasks: baixar ZIP → extrair TXTs → apagar ZIP
    found = missing = 0
    download_tasks = []
    for date_key, seqs in sorted(needed.items()):
        if date_key not in zip_urls:
            log.debug(f"ZIP {date_key} não encontrado no CKAN")
            missing += 1
            continue
        zip_dest = ZIP_DIR / f"{date_key}.zip"
        download_tasks.append((zip_urls[date_key], zip_dest, date_key, seqs))
        found += 1

    log.info(f"ZIPs a baixar: {found}, datas sem ZIP no CKAN: {missing}")

    def process_zip(url, zip_dest, date_key, seqs):
        out_dir = TXT_DIR / date_key
        # Verificar se todos os TXTs já foram extraídos
        already = sum(1 for s in seqs if (out_dir / f"{s}.txt").exists())
        if already == len(seqs):
            return 0, len(seqs)

        if dry_run:
            log.info(f"[DRY-RUN] {date_key}.zip → {len(seqs)} TXTs")
            return 0, 0

        downloaded_zip = download_file(url, zip_dest)
        if not zip_dest.exists():
            return 0, 0

        extracted = extract_txts_from_zip(zip_dest, seqs, out_dir)

        # Apagar o ZIP após extração para economizar disco
        zip_dest.unlink(missing_ok=True)
        return extracted, already

    total_extracted = total_cached = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(process_zip, url, zip_dest, dk, seqs): dk
            for url, zip_dest, dk, seqs in download_tasks
        }
        with tqdm(total=len(download_tasks), desc="ZIPs", unit="zip") as bar:
            for fut in as_completed(futures):
                try:
                    ex, ca = fut.result()
                    total_extracted += ex
                    total_cached += ca
                except Exception as e:
                    log.warning(f"Erro: {e}")
                bar.update(1)

    log.info(
        f"ZIPs — TXTs extraídos: {total_extracted:,}, "
        f"já existentes: {total_cached:,}"
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Coleta dados brutos do STJ para o dataset STJ-SumBR"
    )
    parser.add_argument(
        "--phase",
        choices=["espelhos", "metadados", "zips"],
        help="Fase a executar (omitir com --all)",
    )
    parser.add_argument(
        "--all", action="store_true", help="Executar todas as fases em sequência"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=8,
        help="Número de workers paralelos (default: 8; use 4 para zips)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostrar o que seria baixado sem baixar",
    )
    args = parser.parse_args()

    if not args.phase and not args.all:
        parser.error("Especifique --phase ou --all")

    phases = ["espelhos", "metadados", "zips"] if args.all else [args.phase]
    zip_workers = min(args.workers, 4)  # ZIPs são grandes, limitar paralelismo

    for phase in phases:
        if phase == "espelhos":
            phase_espelhos(args.workers, args.dry_run)
        elif phase == "metadados":
            phase_metadados(args.workers, args.dry_run)
        elif phase == "zips":
            phase_zips(zip_workers, args.dry_run)


if __name__ == "__main__":
    main()
