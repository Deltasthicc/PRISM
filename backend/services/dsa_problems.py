"""A small, original DSA problem bank for the sandbox
(routes/dsa_sandbox.py). One problem per topic in services/curricula.py's
"dsa-fundamentals" curriculum / the legacy TOPIC_GRAPH
(services/knowledge_graph.py) -- deliberately not verbatim LeetCode
questions (copyright), but the same classic pattern per topic, written from
scratch, with real, hand-verified test cases.

Every problem follows one uniform judging protocol so a single harness
(HARNESS below) works for all of them: the learner's submission must define
a function named exactly `solve`; test input arrives as
`{"args": [...]}` JSON on stdin, and the harness prints
`json.dumps(solve(*args))` -- so `expected_output` for each test case is
just `json.dumps(expected)`. This keeps every test case an exact-string
Judge0 comparison (see services/judge_client.py) instead of needing custom
per-problem diffing logic.

Tree/BST problems represent the tree as a LeetCode-style level-order array
(missing children as `null`/None) rather than requiring the learner to
define their own Node class for judged I/O -- the learner's `solve` is free
to build whatever internal structure it wants from that array.
"""
import json

HARNESS = (
    "\n\nimport sys, json\n"
    "_data = json.loads(sys.stdin.read())\n"
    "print(json.dumps(solve(*_data[\"args\"])))\n"
)


def _case(args: list, expected) -> dict:
    return {
        "args": args,
        "stdin": json.dumps({"args": args}),
        "expected_output": json.dumps(expected),
    }


PROBLEMS = [
    {
        "id": "arrays_pair_sum_indices",
        "competency_id": "arrays",
        "topic_label": "Arrays",
        "difficulty": "easy",
        "title": "Pair Sum Indices",
        "prompt": (
            "Given a list of integers `nums` and an integer `target`, return the "
            "indices `[i, j]` (with `i < j`) of the two numbers that add up to "
            "`target`. Exactly one valid pair is guaranteed to exist."
        ),
        "starter_code": (
            "def solve(nums, target):\n"
            "    # Return [i, j], i < j, such that nums[i] + nums[j] == target.\n"
            "    pass\n"
        ),
        "test_cases": [
            _case([[2, 7, 11, 15], 9], [0, 1]),
            _case([[3, 2, 4], 6], [1, 2]),
            _case([[1, 5, 3, 7, 9], 12], [1, 3]),
        ],
    },
    {
        "id": "linked_lists_middle_value",
        "competency_id": "linked_lists",
        "topic_label": "Linked Lists",
        "difficulty": "easy",
        "title": "Middle of the List",
        "prompt": (
            "A singly linked list is given as a plain list of its node values, "
            "`values`. Using the classic slow/fast-pointer idea (don't just index "
            "the middle directly -- walk it), return the value at the middle node. "
            "If there are two middle nodes, return the second one."
        ),
        "starter_code": (
            "def solve(values):\n"
            "    # values represents a singly linked list, head to tail.\n"
            "    # Return the middle value (the second of two, if the list is even length).\n"
            "    pass\n"
        ),
        "test_cases": [
            _case([[1, 2, 3, 4, 5]], 3),
            _case([[1, 2, 3, 4, 5, 6]], 4),
            _case([[7]], 7),
        ],
    },
    {
        "id": "stacks_queues_balanced_brackets",
        "competency_id": "stacks_queues",
        "topic_label": "Stacks & Queues",
        "difficulty": "easy",
        "title": "Balanced Brackets",
        "prompt": (
            "Given a string `s` containing only the characters `()[]{}`, return "
            "True if every bracket is properly closed and nested, False otherwise."
        ),
        "starter_code": (
            "def solve(s):\n"
            "    # Return True if s's brackets are balanced and properly nested.\n"
            "    pass\n"
        ),
        "test_cases": [
            _case(["()[]{}"], True),
            _case(["(]"], False),
            _case(["{[()]}"], True),
            _case(["((("], False),
        ],
    },
    {
        "id": "binary_search_find_index",
        "competency_id": "binary_search",
        "topic_label": "Binary Search",
        "difficulty": "easy",
        "title": "Find in Sorted Array",
        "prompt": (
            "Given a sorted list of distinct integers `nums` and an integer "
            "`target`, return the index of `target` in `nums`, or -1 if it isn't "
            "present. Must run in O(log n) -- a linear scan defeats the point of "
            "this exercise, even though the judge only checks the returned value."
        ),
        "starter_code": (
            "def solve(nums, target):\n"
            "    # Binary search: return the index of target, or -1.\n"
            "    pass\n"
        ),
        "test_cases": [
            _case([[1, 3, 5, 7, 9, 11], 7], 3),
            _case([[1, 3, 5, 7, 9, 11], 4], -1),
            _case([[2], 2], 0),
        ],
    },
    {
        "id": "recursion_count_ways_to_climb",
        "competency_id": "recursion",
        "topic_label": "Recursion",
        "difficulty": "medium",
        "title": "Ways to Climb",
        "prompt": (
            "A staircase has `n` steps. From any step you may advance 1 or 2 "
            "steps at a time. Return the number of distinct ways to reach the "
            "top, expressed with a recursive relation (memoize it however you "
            "like -- the judge only checks the returned count)."
        ),
        "starter_code": (
            "def solve(n):\n"
            "    # Return the number of distinct ways to climb n steps, 1 or 2 at a time.\n"
            "    pass\n"
        ),
        "test_cases": [
            _case([4], 5),
            _case([5], 8),
            _case([1], 1),
        ],
    },
    {
        "id": "trees_level_order_sum",
        "competency_id": "trees",
        "topic_label": "Trees",
        "difficulty": "medium",
        "title": "Sum at Level",
        "prompt": (
            "A binary tree is given as a level-order array `level_order`, the "
            "same convention LeetCode uses: read left to right, top to bottom, "
            "with `null` for a missing child (its own children are omitted, not "
            "padded further). Given a 0-indexed `level_index` (root is level 0), "
            "return the sum of all node values at that level."
        ),
        "starter_code": (
            "def solve(level_order, level_index):\n"
            "    # level_order: LeetCode-style level-order array, null = missing child.\n"
            "    # Return the sum of node values at level_index (root = level 0).\n"
            "    pass\n"
        ),
        "test_cases": [
            _case([[3, 9, 20, None, None, 15, 7], 2], 22),
            _case([[1, 2, 3, 4, 5, 6, 7], 1], 5),
            _case([[5], 0], 5),
        ],
    },
    {
        "id": "binary_search_tree_validate",
        "competency_id": "binary_search_tree",
        "topic_label": "Binary Search Trees",
        "difficulty": "medium",
        "title": "Validate BST",
        "prompt": (
            "A binary tree is given as a level-order array `level_order` (same "
            "convention as the Trees problem: null = missing child). Return True "
            "if it is a valid binary search tree (every node's value is strictly "
            "between the bounds implied by its ancestors), False otherwise."
        ),
        "starter_code": (
            "def solve(level_order):\n"
            "    # level_order: LeetCode-style level-order array, null = missing child.\n"
            "    # Return True if it is a valid BST.\n"
            "    pass\n"
        ),
        "test_cases": [
            _case([[5, 3, 8, 1, 4, 7, 9]], True),
            _case([[10, 5, 15, None, None, 6, 20]], False),
            _case([[1]], True),
        ],
    },
    {
        "id": "heaps_kth_largest",
        "competency_id": "heaps",
        "topic_label": "Heaps",
        "difficulty": "medium",
        "title": "Kth Largest Element",
        "prompt": (
            "Given a list of integers `nums` and an integer `k`, return the "
            "k-th largest element (k=1 means the largest). A heap-based "
            "selection is the point of the exercise, even though the judge "
            "only checks the returned value."
        ),
        "starter_code": (
            "def solve(nums, k):\n"
            "    # Return the k-th largest element of nums (k=1 -> the largest).\n"
            "    pass\n"
        ),
        "test_cases": [
            _case([[3, 2, 1, 5, 6, 4], 2], 5),
            _case([[3, 2, 3, 1, 2, 4, 5, 5, 6], 4], 4),
            _case([[1], 1], 1),
        ],
    },
    {
        "id": "graphs_shortest_path_length",
        "competency_id": "graphs",
        "topic_label": "Graphs",
        "difficulty": "hard",
        "title": "Shortest Path Length",
        "prompt": (
            "An unweighted, undirected graph is given as an adjacency list "
            "`adjacency` (a list of lists; `adjacency[i]` holds the neighbors of "
            "node `i`). Given `start` and `end` node indices, return the number "
            "of edges on the shortest path between them, or -1 if no path exists."
        ),
        "starter_code": (
            "def solve(adjacency, start, end):\n"
            "    # adjacency[i] = list of neighbors of node i.\n"
            "    # Return the shortest path length (edge count) from start to end, or -1.\n"
            "    pass\n"
        ),
        "test_cases": [
            _case([[[1, 2], [0, 3], [0, 3], [1, 2]], 0, 3], 2),
            _case([[[1], [0, 2], [1]], 0, 2], 2),
            _case([[[1], [0], [3], [2]], 0, 3], -1),
        ],
    },
    {
        "id": "dynamic_programming_max_non_adjacent_sum",
        "competency_id": "dynamic_programming",
        "topic_label": "Dynamic Programming",
        "difficulty": "hard",
        "title": "Max Non-Adjacent Sum",
        "prompt": (
            "Given a list of non-negative integers `nums`, return the maximum "
            "sum achievable by choosing a subset of elements such that no two "
            "chosen elements are adjacent in the original list."
        ),
        "starter_code": (
            "def solve(nums):\n"
            "    # Return the max sum of a subset with no two adjacent elements chosen.\n"
            "    pass\n"
        ),
        "test_cases": [
            _case([[2, 7, 9, 3, 1]], 12),
            _case([[5, 1, 1, 5]], 10),
            _case([[]], 0),
        ],
    },
    {
        "id": "sorting_algorithms_kth_smallest",
        "competency_id": "sorting_algorithms",
        "topic_label": "Sorting Algorithms",
        "difficulty": "easy",
        "title": "Kth Smallest After Sort",
        "prompt": (
            "Given a list of integers `nums` and an integer `k` (1-indexed), "
            "return the k-th smallest element once `nums` is sorted."
        ),
        "starter_code": (
            "def solve(nums, k):\n"
            "    # Return the k-th smallest element of nums, 1-indexed.\n"
            "    pass\n"
        ),
        "test_cases": [
            _case([[5, 3, 8, 1, 9, 2], 3], 3),
            _case([[7, 7, 7], 2], 7),
            _case([[10, 1], 1], 1),
        ],
    },
]

PROBLEMS_BY_ID = {problem["id"]: problem for problem in PROBLEMS}


def public_problem(problem: dict) -> dict:
    """The learner-facing view -- omits `expected_output`/`args` per test
    case (a learner can still see the input to debug against, just not
    prove correctness by reading the answer off the wire)."""
    return {
        "id": problem["id"],
        "competency_id": problem["competency_id"],
        "topic_label": problem["topic_label"],
        "difficulty": problem["difficulty"],
        "title": problem["title"],
        "prompt": problem["prompt"],
        "starter_code": problem["starter_code"],
        "test_case_count": len(problem["test_cases"]),
        "sample_input": problem["test_cases"][0]["args"],
    }
