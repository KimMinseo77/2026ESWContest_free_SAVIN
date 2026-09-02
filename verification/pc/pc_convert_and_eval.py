import argparse
import os
import time
import csv
import shutil

from ultralytics import YOLO


def parse_args():
    p = argparse.ArgumentParser(description="PC 포맷별 mAP/속도 비교 (1단계)")
    p.add_argument("--weights", required=True, help="원본 .pt 파일 경로")
    p.add_argument(
        "--data", required=True, help="data.yaml 경로 (train/val/test 키가 이미 정의되어 있어야 함)"
    )
    p.add_argument(
        "--eval_split",
        default="test",
        choices=["test", "val"],
        help="mAP 채점에 쓸 split (기본값: test)",
    )
    p.add_argument(
        "--calib_split",
        default="val",
        choices=["test", "val", "train"],
        help="INT8 calibration에 쓸 split (기본값: val)",
    )
    p.add_argument("--imgsz", type=int, default=640, help="입력 이미지 크기")
    p.add_argument("--outdir", default="./step1_results", help="결과 저장 폴더")
    p.add_argument("--batch", type=int, default=1, help="검증/속도측정 배치 크기")
    p.add_argument(
        "--skip_int8",
        action="store_true",
        help="INT8 변환을 건너뜀 (calibration 데이터가 준비 안 된 경우)",
    )
    return p.parse_args()


def evaluate_model(model_path, data_yaml, imgsz, batch, label, split, results_list):
    """모델을 로드해서 mAP를 측정하고 결과 리스트에 기록 (split: 'test' 또는 'val')"""
    print(f"\n{'=' * 60}\n[평가 중] {label} (split={split}): {model_path}\n{'=' * 60}")

    model = YOLO(model_path)

    # mAP 측정 
    metrics = model.val(data=data_yaml, imgsz=imgsz, batch=batch, split=split, verbose=False)
    map50 = metrics.box.map50
    map5095 = metrics.box.map
    class_names = metrics.names 
    per_class_map5095 = metrics.box.maps  

    # 추론 속도 측정
    import yaml

    with open(data_yaml, "r", encoding="utf-8") as f:
        data_cfg = yaml.safe_load(f)

    # data.yaml 파일이 있는 폴더를 기준 경로로 사용
    yaml_dir = os.path.dirname(os.path.abspath(data_yaml))
    base_path = data_cfg.get("path", yaml_dir)
    if not os.path.isabs(base_path):
        base_path = os.path.join(yaml_dir, base_path)

    split_rel = data_cfg.get(split)
    if split_rel is None:
        raise ValueError(f"data.yaml에 '{split}' 경로없음.")

    split_dir = split_rel if os.path.isabs(split_rel) else os.path.join(base_path, split_rel)
    if os.path.isdir(split_dir):
        candidates = [
            os.path.join(split_dir, f)
            for f in os.listdir(split_dir)
            if f.lower().endswith((".jpg", ".jpeg", ".png"))
        ]
    else:
        candidates = [split_dir]

    if not candidates:
        raise FileNotFoundError(f"'{split}' 이미지 경로에서 이미지를 찾을 수 없음: {split_dir}")

    sample_img = candidates[0]

    for _ in range(5):
        model.predict(sample_img, imgsz=imgsz, verbose=False)

    # 측정
    n_runs = 30
    t0 = time.perf_counter()
    for _ in range(n_runs):
        model.predict(sample_img, imgsz=imgsz, verbose=False)
    t1 = time.perf_counter()
    avg_latency_ms = (t1 - t0) / n_runs * 1000

    print(f"  mAP50      : {map50:.4f}")
    print(f"  mAP50-95   : {map5095:.4f}")
    print(f"  평균 추론시간: {avg_latency_ms:.2f} ms")
    print(f"  [클래스별 mAP50-95]")

    per_class_result = {}
    for idx, cname in class_names.items():
        val = per_class_map5095[idx] if idx < len(per_class_map5095) else float("nan")
        per_class_result[cname] = round(float(val), 4)
        print(f"    - {cname:<15}: {val:.4f}")

    result_row = {
        "format": label,
        "path": str(model_path),
        "mAP50": round(map50, 4),
        "mAP50-95": round(map5095, 4),
        "avg_latency_ms": round(avg_latency_ms, 2),
    }
    result_row.update({f"AP50-95_{k}": v for k, v in per_class_result.items()})

    results_list.append(result_row)


def main():
    args = parse_args()
    os.makedirs(args.outdir, exist_ok=True)
    results = []

    # 0) 원본 .pt 평가
    evaluate_model(
        args.weights, args.data, args.imgsz, args.batch, "pt (원본)", args.eval_split, results
    )

    # 1) .onnx FP32 export + 평가
    model = YOLO(args.weights)  # 매 export마다 새로 로드
    onnx_fp32_path = model.export(format="onnx", imgsz=args.imgsz, half=False, simplify=True)
    onnx_fp32_dest = os.path.join(args.outdir, "model_fp32.onnx")
    shutil.move(str(onnx_fp32_path), onnx_fp32_dest)
    evaluate_model(
        onnx_fp32_dest, args.data, args.imgsz, args.batch, "onnx-fp32", args.eval_split, results
    )

    # 2) .onnx INT8 export + 평가
    #  *FP16 단계는 CPU 전용 노트북이라 제외
    if not args.skip_int8:
        model = YOLO(args.weights)
        onnx_int8_path = model.export(
            format="onnx",
            imgsz=args.imgsz,
            int8=True,
            data=args.data,
            split=args.calib_split,  # calibration에 쓸 split
            simplify=True,
        )
        onnx_int8_dest = os.path.join(args.outdir, "model_int8.onnx")
        shutil.move(str(onnx_int8_path), onnx_int8_dest)
        evaluate_model(
            onnx_int8_dest, args.data, args.imgsz, args.batch, "onnx-int8", args.eval_split, results
        )
    else:
        print("\nskip_int8 지정됨: INT8 변환/평가 건너뜀.")


    # 결과 CSV 저장
    csv_path = os.path.join(args.outdir, "results.csv")
    fieldnames = ["format", "path", "mAP50", "mAP50-95", "avg_latency_ms"]
    extra_cols = []
    for r in results:
        for k in r.keys():
            if k.startswith("AP50-95_") and k not in extra_cols:
                extra_cols.append(k)
    fieldnames += extra_cols

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print(f"\n{'=' * 60}\n[완료]: {csv_path}\n{'=' * 60}")
    for r in results:
        print(r)


if __name__ == "__main__":
    main()
