# Benchmarking Guide

Run the benchmark CLI from the repository root to collect latency, throughput, cold start, and memory measurements for a fixed corpus.

```powershell
uv run python -m benchmarks.engine_benchmark `
  --iterations 100 `
  --warmups 10 `
  --output benchmarks/results/local.json
```

The resulting JSON contains percentile values, throughput, cold start, peak memory, and environment metadata. Use it to compare regressions across environments and engine profiles.
