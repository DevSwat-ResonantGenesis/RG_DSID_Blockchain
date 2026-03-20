#!/bin/bash
# Blockchain Service Integration Test Runner
# Author: Agent 7 - ResonantGenesis Team
# Created: February 21, 2026

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "=========================================="
echo "ResonantGenesis Blockchain Service Tests"
echo "=========================================="
echo ""

# Set test environment
export TESTING=true
export PYTHONPATH="$PROJECT_ROOT:$PROJECT_ROOT/blockchain_service:$PYTHONPATH"

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo "Installing pytest..."
    pip install pytest pytest-asyncio httpx
fi

# Run tests with different options
case "${1:-default}" in
    "verbose"|"-v")
        echo "Running all tests in verbose mode..."
        pytest "$SCRIPT_DIR" -v --tb=long
        ;;
    "quiet"|"-q")
        echo "Running all tests in quiet mode..."
        pytest "$SCRIPT_DIR" -q
        ;;
    "coverage"|"-c")
        echo "Running tests with coverage..."
        pip install pytest-cov 2>/dev/null || true
        pytest "$SCRIPT_DIR" -v --cov=app --cov-report=term-missing
        ;;
    "dsid")
        echo "Running DSID tests only..."
        pytest "$SCRIPT_DIR" -v -k "DSID or dsid"
        ;;
    "blocks")
        echo "Running block tests only..."
        pytest "$SCRIPT_DIR" -v -k "Block or block"
        ;;
    "transactions")
        echo "Running transaction tests only..."
        pytest "$SCRIPT_DIR" -v -k "Transaction or transaction"
        ;;
    "contracts")
        echo "Running smart contract tests only..."
        pytest "$SCRIPT_DIR" -v -k "Contract or contract"
        ;;
    "consensus")
        echo "Running consensus tests only..."
        pytest "$SCRIPT_DIR" -v -k "Consensus or consensus"
        ;;
    "governance")
        echo "Running governance tests only..."
        pytest "$SCRIPT_DIR" -v -k "Governance or governance"
        ;;
    *)
        echo "Running all tests..."
        pytest "$SCRIPT_DIR" -v --tb=short
        ;;
esac

echo ""
echo "=========================================="
echo "Blockchain tests completed!"
echo "=========================================="
