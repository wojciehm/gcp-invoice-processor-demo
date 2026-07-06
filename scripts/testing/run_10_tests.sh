#!/bin/bash
echo "🧹 Clearing buckets..."
gsutil -m rm -f gs://invoice-demo-raw-invoices/** || true
gsutil -m rm -f gs://invoice-demo-os-processed-results/** || true
gsutil -m rm -f gs://invoice-demo-ge-processed-results/** || true

echo "✅ Buckets cleared. Starting 10 E2E tests..."
for i in {1..10}; do
    echo "==================================="
    echo "▶️ RUN $i of 10"
    echo "==================================="
    venv/bin/python scripts/testing/test_e2e_pipeline.py
    if [ $? -ne 0 ]; then
        echo "❌ Run $i failed!"
        exit 1
    fi
done
echo "🎉 ALL 10 RUNS PASSED!"
