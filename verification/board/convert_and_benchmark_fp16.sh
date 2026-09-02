#!/bin/bash
set -e

ONNX_PATH="${1:-model_fp32.onnx}"
ENGINE_PATH="${ONNX_PATH%.onnx}_fp16.engine"
TRTEXEC="/usr/src/tensorrt/bin/trtexec"

if [ ! -f "$ONNX_PATH" ]; then
  echo "[오류] onnx 파일을 찾을 수 없습니다: $ONNX_PATH"
  exit 1
fi

echo "[시작] $ONNX_PATH -> $ENGINE_PATH (FP16)"

"$TRTEXEC" \
  --onnx="$ONNX_PATH" \
  --saveEngine="$ENGINE_PATH" \
  --fp16 \
  --workspace=1024

echo "[완료] 엔진 저장됨: $ENGINE_PATH"
