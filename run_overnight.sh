#!/usr/bin/env bash
# run_overnight.sh — executa o pipeline de coleta completo em background
#
# Uso:
#   chmod +x run_overnight.sh
#   ./run_overnight.sh            # roda tudo (fases 1+2+3)
#   ./run_overnight.sh --phase zips   # só os ZIPs (se 1+2 já foram feitas)
#   ./run_overnight.sh --dry-run  # simula sem baixar nada

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
LOG_FILE="$LOG_DIR/fetch_${TIMESTAMP}.log"

mkdir -p "$LOG_DIR"

# Argumentos passados ao fetch.py (default: --all --workers 8)
FETCH_ARGS="${*:---all --workers 8}"

echo "STJ-SumBR — coleta iniciada em $(date)"
echo "Log: $LOG_FILE"
echo "Argumentos: $FETCH_ARGS"
echo ""

# Verifica espaço disponível (avisa se < 20 GB)
AVAIL_KB=$(df -k "$SCRIPT_DIR" | awk 'NR==2 {print $4}')
AVAIL_GB=$(( AVAIL_KB / 1024 / 1024 ))
if (( AVAIL_GB < 20 )); then
    echo "AVISO: apenas ${AVAIL_GB} GB disponíveis. Recomendado >= 20 GB para a fase de ZIPs."
    echo "Continue mesmo assim? [s/N]"
    read -r resp
    [[ "$resp" =~ ^[sS]$ ]] || { echo "Abortado."; exit 1; }
fi

# Registra PID para poder matar se necessário: kill $(cat logs/fetch.pid)
PID_FILE="$LOG_DIR/fetch.pid"

nohup uv run python src/fetch.py $FETCH_ARGS \
    >> "$LOG_FILE" 2>&1 &

PID=$!
echo $PID > "$PID_FILE"

echo "Rodando em background — PID $PID"
echo ""
echo "Acompanhar progresso:"
echo "  tail -f $LOG_FILE"
echo ""
echo "Parar se necessário:"
echo "  kill \$(cat $PID_FILE)"
