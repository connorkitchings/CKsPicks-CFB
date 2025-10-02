#!/bin/bash
# Quick status check for hyperparameter optimization

echo "============================================================"
echo "HYPERPARAMETER OPTIMIZATION STATUS"
echo "============================================================"
echo ""

# Check running processes
echo "Running Processes:"
echo "------------------"
PROCS=$(ps aux | grep "optimize_hyperparameters" | grep -v grep | grep -v "check_optimization")
if [ -z "$PROCS" ]; then
    echo "❌ No optimization processes running"
else
    echo "$PROCS" | awk '{print "  ✓ PID:", $2, "CPU:", $3"%", "Started:", $9}'
fi
echo ""

# Check for results
echo "Results Status:"
echo "---------------"
if [ -f "./reports/optimization/hyperparameter_optimization_results.json" ]; then
    echo "  ✅ Results file found!"
    echo "  📊 Review with: cat reports/optimization/hyperparameter_optimization_results.json"
else
    echo "  ⏳ Waiting for results..."
fi
echo ""

# Show log sizes
echo "Log Files:"
echo "----------"
if [ -f "/tmp/hyperopt.log" ]; then
    SIZE=$(ls -lh /tmp/hyperopt.log | awk '{print $5}')
    echo "  Totals log: $SIZE (/tmp/hyperopt.log)"
else
    echo "  Totals log: Not found"
fi

if [ -f "/tmp/hyperopt_spreads.log" ]; then
    SIZE=$(ls -lh /tmp/hyperopt_spreads.log | awk '{print $5}')
    echo "  Spreads log: $SIZE (/tmp/hyperopt_spreads.log)"
else
    echo "  Spreads log: Not found"
fi
echo ""

echo "Next Steps:"
echo "-----------"
if [ -f "./reports/optimization/hyperparameter_optimization_results.json" ]; then
    echo "  ✅ Run: uv run python scripts/apply_hyperparameter_results.py"
else
    echo "  ⏳ Wait for optimization to complete (~5-15 minutes)"
    echo "  💡 Monitor with: tail -f /tmp/hyperopt.log"
fi
echo ""
echo "============================================================"
