| Model | Case | Expected | Run | Model verdict correct | Tool outcome correct | Findings (section:verdict/status) | Seconds |
|---|---|---|---|---|---|---|---|
| qwen3:4b | tc01 | stale + passing fix | 1 | yes | yes | s3:stale/passed | 35 |
| qwen3:4b | tc01 | stale + passing fix | 2 | yes | yes | s3:stale/passed | 23 |
| qwen3:4b | tc01 | stale + passing fix | 3 | yes | yes | s3:stale/passed | 22 |
| qwen3:4b | tc02 | still_accurate, no fix | 1 | **no** | yes | s2:stale/rejected | 37 |
| qwen3:4b | tc02 | still_accurate, no fix | 2 | **no** | yes | s2:stale/rejected | 26 |
| qwen3:4b | tc02 | still_accurate, no fix | 3 | **no** | yes | s2:stale/rejected | 25 |
| qwen3:4b | tc06 | unsure, no accepted fix | 1 | **no** | **no** | s2:stale/passed | 47 |
| qwen3:4b | tc06 | unsure, no accepted fix | 2 | **no** | **no** | s2:stale/passed | 19 |
| qwen3:4b | tc06 | unsure, no accepted fix | 3 | **no** | **no** | s2:stale/passed | 18 |
| qwen3:4b | tc07 | stale + passing fix | 1 | yes | yes | s2:stale/passed | 27 |
| qwen3:4b | tc07 | stale + passing fix | 2 | yes | yes | s2:stale/passed | 27 |
| qwen3:4b | tc07 | stale + passing fix | 3 | yes | yes | s2:stale/passed | 23 |
| gemma3:4b | tc01 | stale + passing fix | 1 | ERROR | ERROR | exit 3: error: Ollama request failed: timed out | 301 |
| gemma3:4b | tc01 | stale + passing fix | 2 | yes | **no** | s1:stale/rejected, s2:still_accurate/rejected, s3:stale/rejected, s4:stale/rejected | 74 |
| gemma3:4b | tc01 | stale + passing fix | 3 | yes | **no** | s1:stale/rejected, s2:still_accurate/rejected, s3:stale/rejected, s4:stale/rejected | 48 |
| gemma3:4b | tc02 | still_accurate, no fix | 1 | **no** | yes | s1:stale/rejected, s2:stale/rejected | 31 |
| gemma3:4b | tc02 | still_accurate, no fix | 2 | **no** | yes | s1:stale/rejected, s2:stale/rejected | 26 |
| gemma3:4b | tc02 | still_accurate, no fix | 3 | **no** | yes | s1:stale/rejected, s2:stale/rejected | 28 |
| gemma3:4b | tc06 | unsure, no accepted fix | 1 | **no** | **no** | s1:stale/rejected, s2:stale/rejected | 30 |
| gemma3:4b | tc06 | unsure, no accepted fix | 2 | **no** | **no** | s1:stale/rejected, s2:stale/rejected | 26 |
| gemma3:4b | tc06 | unsure, no accepted fix | 3 | **no** | **no** | s1:stale/rejected, s2:stale/rejected | 28 |
| gemma3:4b | tc07 | stale + passing fix | 1 | **no** | **no** | s1:stale/rejected, s2:still_accurate/not_applicable | 30 |
| gemma3:4b | tc07 | stale + passing fix | 2 | **no** | **no** | s1:stale/rejected, s2:still_accurate/not_applicable | 29 |
| gemma3:4b | tc07 | stale + passing fix | 3 | **no** | **no** | s1:stale/rejected, s2:still_accurate/not_applicable | 31 |
