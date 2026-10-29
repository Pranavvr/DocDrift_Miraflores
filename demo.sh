#!/usr/bin/env bash
# DocDrift demo: one representative case, one guardrail rejection, one invalid input.
# Usage: ./demo.sh [model]   (default qwen3:4b). Falls back to the mock if Ollama isn't usable.
cd "$(dirname "$0")"
MODEL="${1:-qwen3:4b}"

step() { printf '\n\033[1m=== %s ===\033[0m\n$ %s\n\n' "$1" "$2"; }

step "1. Representative case (TC-01): function now returns None, README says it raises KeyError" \
     "python3 main.py --diff samples/tc01/change.diff --docs samples/tc01/README.md --model $MODEL"
python3 main.py --diff samples/tc01/change.diff --docs samples/tc01/README.md --model "$MODEL"
code=$?
if [ "$code" -eq 3 ]; then
  echo
  echo "(Model backend unavailable, exit 3. Re-running with the labeled mock backend.)"
  python3 main.py --diff samples/tc01/change.diff --docs samples/tc01/README.md \
    --backend mock --mock-response tests/fixtures/tc01_stale.json
fi

step "2. Guardrail rejection (TC-03, mock): model suggests '10 retries', diff says 5" \
     "python3 main.py --diff samples/tc03/change.diff --docs samples/tc03/README.md --backend mock --mock-response tests/fixtures/tc03_unsupported_value.json"
python3 main.py --diff samples/tc03/change.diff --docs samples/tc03/README.md \
  --backend mock --mock-response tests/fixtures/tc03_unsupported_value.json

step "3. Invalid input (TC-04): not a unified diff" \
     "python3 main.py --diff samples/tc04/change.diff --docs samples/tc04/README.md"
python3 main.py --diff samples/tc04/change.diff --docs samples/tc04/README.md
echo "exit code: $? (1 = invalid input; the model was not called)"
