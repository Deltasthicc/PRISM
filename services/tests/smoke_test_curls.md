# Smoke test curl commands

Start the server first:

```bash
cd services
uvicorn main:app --reload --port 8001
```

All payloads below use `MOCK_ACCURACY_HISTORY_INTERMEDIATE` from
`mocks/mock_data.py` (arrays=0.8, linked_lists=0.6, binary_search=0.4,
recursion=0.2, stacks_queues absent) so the RL tuner and knowledge graph
make real, visibly different decisions instead of just falling back to
their "no data" defaults.

## GET /health

```bash
curl http://localhost:8001/health
```

## POST /ai/question/generate

```bash
curl -X POST http://localhost:8001/ai/question/generate \
  -H "Content-Type: application/json" \
  -d '{
    "player_id": "550e8400-e29b-41d4-a716-446655440000",
    "topic": "binary_search",
    "difficulty": "medium",
    "domain": "Data Structures & Algorithms"
  }'
```

## POST /ai/answer/judge

```bash
curl -X POST http://localhost:8001/ai/answer/judge \
  -H "Content-Type: application/json" \
  -d '{
    "question_id": "11111111-1111-1111-1111-111111111111",
    "player_answer": "It splits the array in half each time and checks the middle value to find the target",
    "expected_answer": "Binary search works by repeatedly dividing the search interval in half and comparing the middle element",
    "question": "Explain how binary search works."
  }'
```

## POST /ai/difficulty/next

Topic "linked_lists" has recent_accuracy=0.6 -> expect `"difficulty": "medium"`
most of the time (epsilon=0.1 exploration may occasionally return something else).

```bash
curl -X POST http://localhost:8001/ai/difficulty/next \
  -H "Content-Type: application/json" \
  -d '{
    "player_id": "550e8400-e29b-41d4-a716-446655440000",
    "topic": "linked_lists",
    "accuracy_history": {
      "arrays":        { "attempts": 12, "correct": 11, "recent_accuracy": 0.8, "last_5_results": [true, true, true, true, false] },
      "linked_lists":  { "attempts": 8,  "correct": 5,  "recent_accuracy": 0.6, "last_5_results": [true, false, true, false, true] },
      "binary_search": { "attempts": 7,  "correct": 3,  "recent_accuracy": 0.4, "last_5_results": [false, true, false, false, true] },
      "recursion":     { "attempts": 9,  "correct": 2,  "recent_accuracy": 0.2, "last_5_results": [false, false, true, false, false] }
    }
  }'
```

## POST /ai/graph/next-topic

`arrays` (0.8) unlocks linked_lists/binary_search/recursion/stacks_queues, but
`trees` stays locked since neither linked_lists (0.6) nor recursion (0.2) clear
0.65. Expect `next_topic` to be `"recursion"` (weakest unlocked, score 0.8) and
`weak_topics` to include `binary_search` and `recursion`.

```bash
curl -X POST http://localhost:8001/ai/graph/next-topic \
  -H "Content-Type: application/json" \
  -d '{
    "player_id": "550e8400-e29b-41d4-a716-446655440000",
    "accuracy_history": {
      "arrays":        { "attempts": 12, "correct": 11, "recent_accuracy": 0.8, "last_5_results": [true, true, true, true, false] },
      "linked_lists":  { "attempts": 8,  "correct": 5,  "recent_accuracy": 0.6, "last_5_results": [true, false, true, false, true] },
      "binary_search": { "attempts": 7,  "correct": 3,  "recent_accuracy": 0.4, "last_5_results": [false, true, false, false, true] },
      "recursion":     { "attempts": 9,  "correct": 2,  "recent_accuracy": 0.2, "last_5_results": [false, false, true, false, false] }
    }
  }'
```
