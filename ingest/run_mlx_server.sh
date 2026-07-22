#!/usr/bin/env bash
# Launch the local MLX model server for the classifier.
#
# The Homebrew system Python has mlx_lm 0.30.7 / mlx 0.30.6, which crash on generation under
# Python 3.14 ("RuntimeError: There is no Stream(gpu, 0) in current thread"). The versions that
# actually work — proven by a running server's own fingerprint — are mlx_lm 0.31.3 + mlx 0.32.0.
# We install those into a dedicated venv so Homebrew's Python is never touched (PEP 668).
#
#   ./run_mlx_server.sh            # create venv if needed, then serve on :8848
set -euo pipefail
VENV="${AIPI_MLX_VENV:-$HOME/.mlx-venv}"
MODEL="${AIPI_QWEN_MODEL:-mlx-community/Qwen3-30B-A3B-4bit}"
PORT="${AIPI_MLX_PORT:-8848}"
if [ ! -x "$VENV/bin/python" ]; then
  echo "creating venv at $VENV"
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install --quiet --upgrade pip
  "$VENV/bin/pip" install --quiet 'mlx==0.32.0' 'mlx-lm==0.31.3'
fi
echo "serving $MODEL on 127.0.0.1:$PORT (mlx_lm $("$VENV/bin/python" -c 'import mlx_lm;print(mlx_lm.__version__)'))"
exec "$VENV/bin/python" -m mlx_lm server --model "$MODEL" --port "$PORT"
