import json
import pytest
from pathlib import Path
from src.parse import normalize_record, _date_yyyymmdd_to_iso, _area_direito, _parse_ementa_estruturada

# ---------------------------------------------------------------------------
# _date_yyyymmdd_to_iso
# ---------------------------------------------------------------------------

def test_date_conversion_valid():
    assert _date_yyyymmdd_to_iso("20260422") == "2026-04-22"

def test_date_conversion_none():
    assert _date_yyyymmdd_to_iso(None) is None
    assert _date_yyyymmdd_to_iso("") is None

def test_date_conversion_invalid():
    assert _date_yyyymmdd_to_iso("XXXXXXXX") is None


# ---------------------------------------------------------------------------
# _area_direito
# ---------------------------------------------------------------------------

def test_area_map_known():
    assert _area_direito("TERCEIRA TURMA") == "civil"
    assert _area_direito("QUINTA TURMA")   == "penal"
    assert _area_direito("PRIMEIRA TURMA") == "público"
    assert _area_direito("CORTE ESPECIAL") == "misto"

def test_area_map_unknown():
    assert _area_direito("TURMA DESCONHECIDA") is None
    assert _area_direito(None) is None


# ---------------------------------------------------------------------------
# _parse_ementa_estruturada
# ---------------------------------------------------------------------------

EMENTA_ESTRUTURADA = """
DIREITO CIVIL. RECURSO ESPECIAL.
I. CASO EM EXAME
1. Recurso especial interposto contra acórdão do TJSP.
II. QUESTÃO EM DISCUSSÃO
2. Saber se o prazo prescricional se aplica ao caso.
III. RAZÕES DE DECIDIR
3. A jurisprudência consolidada do STJ indica que sim.
IV. DISPOSITIVO
4. Recurso especial provido.
"""

def test_ementa_estruturada_detectada():
    r = _parse_ementa_estruturada(EMENTA_ESTRUTURADA)
    assert r["is_estruturada"] is True

def test_ementa_estruturada_campos():
    r = _parse_ementa_estruturada(EMENTA_ESTRUTURADA)
    assert "Recurso especial interposto" in r["resumo_contexto"]
    assert "prazo prescricional" in r["resumo_instituto"]
    assert "jurisprudência consolidada" in r["resumo_fundamentacao"]
    assert "provido" in r["resumo_entendimento"]

def test_ementa_nao_estruturada():
    r = _parse_ementa_estruturada("DIREITO CIVIL. Ementa simples sem marcadores.")
    assert r["is_estruturada"] is False
    assert r["resumo_contexto"] is None

def test_ementa_estruturada_dispositivo_e_tese():
    ementa = (
        "TEMA.\nI. CASO EM EXAME\nContexto.\n"
        "II. QUESTÃO EM DISCUSSÃO\nQuestão.\n"
        "III. RAZÕES DE DECIDIR\nFundamentação.\n"
        "IV. DISPOSITIVO E TESE\nTese firmada."
    )
    r = _parse_ementa_estruturada(ementa)
    assert r["is_estruturada"] is True
    assert r["resumo_entendimento"] is not None


# ---------------------------------------------------------------------------
# normalize_record
# ---------------------------------------------------------------------------

RAW_RECORD = {
    "numeroProcesso":       "1970097",
    "siglaClasse":          "REsp",
    "numeroRegistro":       "202101050380",
    "nomeOrgaoJulgador":    "TERCEIRA TURMA",
    "dataDecisao":          "20260422",
    "ministroRelator":      "HUMBERTO MARTINS",
    "ementa":               "DIREITO CIVIL. Ementa de teste.",
    "jurisprudenciaCitada": "",
    "referenciasLegislativas": ["LEG:FED LEI:010406 ANO:2002"],
}

def test_normalize_record_basic():
    r = normalize_record(RAW_RECORD)
    assert r is not None
    assert r["id"] == "REsp 1970097"
    assert r["numero_registro"] == "202101050380"
    assert r["area_direito"] == "civil"
    assert r["data_julgamento"] == "2026-04-22"
    assert r["turma"] == "TERCEIRA TURMA"

def test_normalize_record_ementa_none():
    raw = dict(RAW_RECORD, ementa=None)
    assert normalize_record(raw) is None

def test_normalize_record_refs_lista():
    r = normalize_record(RAW_RECORD)
    assert isinstance(r["legislacao_citada"], list)
    assert len(r["legislacao_citada"]) == 1

def test_normalize_record_jurisprudencia_vazia():
    r = normalize_record(RAW_RECORD)
    assert r["jurisprudencia_citada"] is None


# ---------------------------------------------------------------------------
# Integração: processar o arquivo de amostra real
# ---------------------------------------------------------------------------

SAMPLE_FILE = Path("data/raw/espelhos_20260531.json")

@pytest.mark.skipif(not SAMPLE_FILE.exists(), reason="amostra não disponível")
def test_parse_sample_file():
    from src.parse import parse_file
    records, total, discarded = parse_file(SAMPLE_FILE)
    assert total == 737
    assert discarded == 0
    assert len(records) == 737
    structured = sum(1 for r in records if r["is_estruturada"])
    # sabemos que ~7-8% são estruturados
    assert structured > 0
