"""Reproduce this dated comparison; no corpus mutation or network access."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.metadata
import io
import json
import math
import platform
import statistics
import subprocess
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter_ns

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
TARGETS = ("strict", "balanced", "aggressive", "korcen")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def metrics(cases, predictions):
    counts = dict.fromkeys(("tp", "fp", "fn", "tn"), 0)
    for case in cases:
        expected = case["expected"]
        if expected is None:
            continue
        actual = predictions[case["id"]]
        key = ("tp" if actual else "fn") if expected else ("fp" if actual else "tn")
        counts[key] += 1
    tp, fp, fn, tn = (counts[k] for k in ("tp", "fp", "fn", "tn"))
    return {
        **counts,
        "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / (tp + fn) if tp + fn else None,
        "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None,
        "false_positive_rate": fp / (fp + tn) if fp + tn else None,
    }


def worker(target, payload):
    captured = io.StringIO()
    with contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured):
        if target == "korcen":
            from korcen import korcen

            def check(text):
                return korcen.check(text, foreign=False)
        else:
            from koguard import KoguardEngine

            engine = KoguardEngine(profile=target)
            check = engine.contains
        predictions = {c["id"]: check(c["text"]) for c in payload["cases"]}
        assert all(type(p) is bool for p in predictions.values())
        workloads = {}
        for case in payload["workloads"]:
            text = case["text"]
            expected_result = check(text)
            for _ in range(payload["warmups"]):
                assert check(text) == expected_result
            samples = []
            for _ in range(payload["iterations"]):
                start = perf_counter_ns()
                result = check(text)
                samples.append((perf_counter_ns() - start) / 1_000_000)
                assert result == expected_result
            samples.sort()
            workloads[case["id"]] = {
                "length": len(text),
                "detected": expected_result,
                "p50_ms": statistics.median(samples),
                "p95_ms": samples[math.ceil(len(samples) * 0.95) - 1],
                "calls_per_second": 1000 / statistics.mean(samples),
            }
    return {
        "predictions": predictions,
        "workloads": workloads,
        "suppressed_output": bool(captured.getvalue()),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", choices=TARGETS)
    parser.add_argument("--payload", type=Path)
    parser.add_argument("--env-python", type=Path)
    parser.add_argument("--artifacts", type=Path)
    parser.add_argument("--output", type=Path, default=HERE / "results.json")
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--rounds", type=int, default=3)
    args = parser.parse_args()
    if args.worker:
        print(json.dumps(worker(args.worker, json.loads(args.payload.read_text("utf-8")))))
        return
    if not args.env_python or not args.artifacts or args.iterations < 1 or args.rounds < 1:
        parser.error("positive counts, --env-python and --artifacts are required")
    diagnostic_path = HERE / "diagnostic-cases.json"
    regression_path = ROOT / "evaluation/corpus/provisional-ablation.json"
    cases = json.loads(diagnostic_path.read_text("utf-8"))["cases"]
    for case in json.loads(regression_path.read_text("utf-8"))["cases"]:
        if case["label"] != "review":
            cases.append(
                {
                    "id": case["id"],
                    "text": case["text"],
                    "expected": case["label"] == "positive",
                    "group": "regression",
                }
            )
    assert len({c["id"] for c in cases}) == len(cases)
    pattern = "가나다라마바사아자차카타파하"
    normal = (pattern * 300)[:4096]
    workload_texts = {
        "short-clean": "오늘 저녁에 같이 게임할래?",
        "short-positive": "이런 병신 같은 소리",
        "normal-1024": normal[:1024],
        "normal-4096": normal,
        "positive-tail-4096": normal[:4093] + " 병신",
        "repeated-regression-4096": "이이" + "가" * 4094,
        "obfuscation-short": "시 * 발",
    }
    artifact_dir = args.artifacts.resolve()
    cwd = artifact_dir / "measurement-cwd"
    cwd.mkdir(parents=True, exist_ok=True)
    assert not list(cwd.iterdir()), "Korcen custom-filter working directory must be empty"
    payload_path = artifact_dir / "measurement-input.json"
    payload_path.write_text(
        json.dumps(
            {
                "cases": cases,
                "iterations": args.iterations,
                "warmups": 10,
                "workloads": [{"id": k, "text": v} for k, v in workload_texts.items()],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    runs = {target: [] for target in TARGETS}
    for round_index in range(args.rounds):
        order = TARGETS[round_index % 4 :] + TARGETS[: round_index % 4]
        for target in order:
            completed = subprocess.run(
                [
                    str(args.env_python.resolve()),
                    "-I",
                    "-X",
                    "utf8",
                    str(Path(__file__).resolve()),
                    "--worker",
                    target,
                    "--payload",
                    str(payload_path),
                ],
                cwd=cwd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=120,
                check=True,
            )
            runs[target].append(json.loads(completed.stdout))
            print(f"round {round_index + 1}/{args.rounds}: {target} complete", flush=True)
    results = {}
    for target, rounds in runs.items():
        predictions = rounds[0]["predictions"]
        assert all(r["predictions"] == predictions for r in rounds)
        latency = {}
        for name in workload_texts:
            measured = [r["workloads"][name] for r in rounds]
            assert len({r["detected"] for r in measured}) == 1
            latency[name] = {
                "length": measured[0]["length"],
                "detected": measured[0]["detected"],
                "median_round_p50_ms": statistics.median(r["p50_ms"] for r in measured),
                "median_round_p95_ms": statistics.median(r["p95_ms"] for r in measured),
                "rounds": measured,
            }
        results[target] = {
            "predictions": predictions,
            "latency": latency,
            "groups": {
                g: metrics([c for c in cases if c["group"] == g], predictions)
                for g in sorted({c["group"] for c in cases})
                if g != "policy-boundary"
            },
            "suppressed_output": any(r["suppressed_output"] for r in rounds),
        }
    downloads = json.loads(
        (artifact_dir / "dependencies/download-manifest.json").read_text("utf-8")
    )
    for entry in downloads:
        assert digest(artifact_dir / "dependencies" / entry["filename"]) == entry["sha256"]
        assert importlib.metadata.version(entry["package"]) == entry["version"]
    wheel = artifact_dir / "koguard-0.1.0-py3-none-any.whl"
    report = {
        "kind": "dated-diagnostic-comparison-not-independent-benchmark",
        "generated_at": datetime.now(UTC).isoformat(),
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "iterations_per_round": args.iterations,
        "rounds": args.rounds,
        "warmups": 10,
        "corpus_counts": dict(Counter(c["group"] for c in cases)),
        "inputs": {
            "diagnostic_sha256": digest(diagnostic_path),
            "regression_sha256": digest(regression_path),
        },
        "runner_sha256": digest(Path(__file__)),
        "artifacts": [
            {
                "package": "koguard",
                "version": importlib.metadata.version("koguard"),
                "filename": wheel.name,
                "sha256": digest(wheel),
            },
            *downloads,
        ],
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
