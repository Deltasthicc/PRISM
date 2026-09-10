"""A small, original DSA problem bank for the sandbox
(routes/dsa_sandbox.py). At least one problem per topic in
services/curricula.py's "dsa-fundamentals" curriculum / the legacy
TOPIC_GRAPH (services/knowledge_graph.py) -- deliberately not verbatim
LeetCode questions (copyright), but the same classic pattern per topic,
written from scratch, with real, hand-verified test cases.

Every problem follows one uniform judging protocol so a single harness per
language (services/dsa_lang_gen.py's PY_HARNESS/JS_HARNESS/build_harness())
works for all of them: the learner's submission must define a function
named exactly `solve` (or, for the statically-typed languages, a `Solution`
class with a `solve`/`Solve` method); test input arrives as a bare JSON
array `[...]` of the arguments on stdin, and the harness prints the JSON
result with compact separators -- so `expected_output` for each test case
is `json.dumps(expected, separators=(",", ":"))`, matching every language's
compact output exactly. This keeps every test case an exact-string Judge0
comparison (see services/judge_client.py) instead of needing custom
per-problem diffing logic.

Each problem also carries `arg_types`/`param_names`/`return_type` metadata,
consumed by services/dsa_lang_gen.py to generate the equivalent starter code
and judge harness for Java, C++, C# and JavaScript -- see that module's
docstring for the full design (Judge0 has no JSON library on Java/C++/C#,
so those three carry a small hand-verified minimal JSON parser instead).

Tree/BST problems represent the tree as a LeetCode-style level-order array
(missing children as `null`/None) rather than requiring the learner to
define their own Node class for judged I/O -- the learner's `solve` is free
to build whatever internal structure it wants from that array.
"""
import json

from services import dsa_lang_gen


def _case(args: list, expected) -> dict:
    # Compact separators (no space after ',' or ':') so this matches the
    # compact output every other language's hand-rolled JSON stringifier
    # produces (see services/dsa_lang_gen.py) -- Judge0 does an exact-string
    # comparison against expected_output.
    return {
        "args": args,
        "stdin": json.dumps(args, separators=(",", ":")),
        "expected_output": json.dumps(expected, separators=(",", ":")),
    }


PROBLEMS = [
    {
        "id": "arrays_pair_sum_indices",
        "competency_id": "arrays",
        "topic_label": "Arrays",
        "difficulty": "easy",
        "title": "Pair Sum Indices",
        "param_names": ["nums", "target"],
        "arg_types": ["int[]", "int"],
        "return_type": "int[]",
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
        "param_names": ["values"],
        "arg_types": ["int[]"],
        "return_type": "int",
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
        "param_names": ["s"],
        "arg_types": ["str"],
        "return_type": "bool",
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
        "param_names": ["nums", "target"],
        "arg_types": ["int[]", "int"],
        "return_type": "int",
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
        "param_names": ["n"],
        "arg_types": ["int"],
        "return_type": "int",
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
        "param_names": ["level_order", "level_index"],
        "arg_types": ["nullable_int[]", "int"],
        "return_type": "int",
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
        "param_names": ["level_order"],
        "arg_types": ["nullable_int[]"],
        "return_type": "bool",
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
        "param_names": ["nums", "k"],
        "arg_types": ["int[]", "int"],
        "return_type": "int",
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
        "param_names": ["adjacency", "start", "end"],
        "arg_types": ["int[][]", "int", "int"],
        "return_type": "int",
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
        "param_names": ["nums"],
        "arg_types": ["int[]"],
        "return_type": "int",
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
        "param_names": ["nums", "k"],
        "arg_types": ["int[]", "int"],
        "return_type": "int",
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
    {
        "id": "arrays_move_zeroes",
        "competency_id": "arrays",
        "topic_label": "Arrays",
        "difficulty": "easy",
        "title": "Move Zeroes",
        "param_names": ["nums"],
        "arg_types": ["int[]"],
        "return_type": "int[]",
        "prompt": (
            "Given a list of integers `nums`, return a new list with every 0 "
            "moved to the end, while preserving the relative order of the "
            "non-zero elements."
        ),
        "starter_code": (
            "def solve(nums):\n"
            "    # Return nums with every 0 moved to the end, non-zero order preserved.\n"
            "    pass\n"
        ),
        "test_cases": [
            _case([[0, 1, 0, 3, 12]], [1, 3, 12, 0, 0]),
            _case([[0, 0, 1]], [1, 0, 0]),
            _case([[4, 2, 1]], [4, 2, 1]),
        ],
    },
    {
        "id": "graphs_has_cycle",
        "competency_id": "graphs",
        "topic_label": "Graphs",
        "difficulty": "medium",
        "title": "Detect a Cycle",
        "param_names": ["adjacency"],
        "arg_types": ["int[][]"],
        "return_type": "bool",
        "prompt": (
            "A directed graph is given as an adjacency list `adjacency` (a "
            "list of lists; `adjacency[i]` holds the nodes `i` has an edge "
            "to). Return True if the graph contains a cycle, False otherwise."
        ),
        "starter_code": (
            "def solve(adjacency):\n"
            "    # adjacency[i] = list of nodes with an edge from node i.\n"
            "    # Return True if the directed graph contains a cycle.\n"
            "    pass\n"
        ),
        "test_cases": [
            _case([[[1], [2], [0]]], True),
            _case([[[1], [2], []]], False),
            _case([[[1, 2], [], []]], False),
        ],
    },
    {
        "id": "dynamic_programming_longest_increasing_subsequence",
        "competency_id": "dynamic_programming",
        "topic_label": "Dynamic Programming",
        "difficulty": "hard",
        "title": "Longest Increasing Subsequence",
        "param_names": ["nums"],
        "arg_types": ["int[]"],
        "return_type": "int",
        "prompt": (
            "Given a list of integers `nums`, return the length of the "
            "longest strictly increasing subsequence (elements need not be "
            "contiguous)."
        ),
        "starter_code": (
            "def solve(nums):\n"
            "    # Return the length of the longest strictly increasing subsequence.\n"
            "    pass\n"
        ),
        "test_cases": [
            _case([[10, 9, 2, 5, 3, 7, 101, 18]], 4),
            _case([[0, 1, 0, 3, 2, 3]], 4),
            _case([[7, 7, 7, 7]], 1),
        ],
    },
    {
        "id": "strings_longest_unique_window",
        "competency_id": "arrays",
        "topic_label": "Strings & Sliding Window",
        "difficulty": "medium",
        "title": "Longest Unique Window",
        "param_names": ["text"],
        "arg_types": ["str"],
        "return_type": "int",
        "prompt": (
            "Given a string `text`, return the length of its longest contiguous substring "
            "containing no repeated character. A substring must occupy consecutive positions; "
            "you may not skip characters. Aim for O(n) time by maintaining a sliding window."
        ),
        "starter_code": (
            "def solve(text):\n"
            "    # Return the longest duplicate-free contiguous window length.\n"
            "    pass\n"
        ),
        "test_cases": [
            _case(["abcabcbb"], 3),
            _case(["bbbbb"], 1),
            _case(["pwwkew"], 3),
            _case([""], 0),
        ],
    },
    {
        "id": "hashing_first_unique_value",
        "competency_id": "arrays",
        "topic_label": "Hash Maps",
        "difficulty": "easy",
        "title": "First Unique Value",
        "param_names": ["nums"],
        "arg_types": ["int[]"],
        "return_type": "int",
        "prompt": (
            "Return the first value in `nums` that occurs exactly once in the entire list. "
            "Preserve the original left-to-right order when deciding which unique value is "
            "first. Return -1 when every value is repeated."
        ),
        "starter_code": (
            "def solve(nums):\n"
            "    # Count first, then return the first value whose count is one.\n"
            "    pass\n"
        ),
        "test_cases": [
            _case([[4, 5, 1, 2, 1, 4, 2]], 5),
            _case([[7, 7, 8, 8]], -1),
            _case([[9]], 9),
        ],
    },
    {
        "id": "two_pointers_sorted_squares",
        "competency_id": "arrays",
        "topic_label": "Two Pointers",
        "difficulty": "easy",
        "title": "Sorted Squares",
        "param_names": ["nums"],
        "arg_types": ["int[]"],
        "return_type": "int[]",
        "prompt": (
            "`nums` is sorted in non-decreasing order and may contain negative values. "
            "Return the square of every value, also in non-decreasing order. Use two pointers "
            "to build the answer in O(n) time rather than sorting the squares again."
        ),
        "starter_code": (
            "def solve(nums):\n"
            "    # Compare absolute values at the left and right ends.\n"
            "    pass\n"
        ),
        "test_cases": [
            _case([[-4, -1, 0, 3, 10]], [0, 1, 9, 16, 100]),
            _case([[-7, -3, 2, 3, 11]], [4, 9, 9, 49, 121]),
            _case([[]], []),
        ],
    },
    {
        "id": "backtracking_ordered_subsets",
        "competency_id": "recursion",
        "topic_label": "Backtracking",
        "difficulty": "medium",
        "title": "Build Every Subset",
        "param_names": ["nums"],
        "arg_types": ["int[]"],
        "return_type": "int[][]",
        "prompt": (
            "Given a list of distinct integers `nums`, return every subset. Preserve the input "
            "order inside each subset, and return subsets in depth-first include/exclude order: "
            "first the branch that excludes the current value, then the branch that includes it."
        ),
        "starter_code": (
            "def solve(nums):\n"
            "    # Backtrack: explore exclude first, then include.\n"
            "    pass\n"
        ),
        "test_cases": [
            _case([[1, 2]], [[], [2], [1], [1, 2]]),
            _case([[3]], [[], [3]]),
            _case([[]], [[]]),
        ],
    },
    {
        "id": "sorting_merge_intervals",
        "competency_id": "sorting_algorithms",
        "topic_label": "Greedy Intervals",
        "difficulty": "medium",
        "title": "Merge Overlapping Windows",
        "param_names": ["intervals"],
        "arg_types": ["int[][]"],
        "return_type": "int[][]",
        "prompt": (
            "Each pair `[start, end]` describes a closed interval. Merge every pair of intervals "
            "that overlap or touch, and return the disjoint merged intervals ordered by start. "
            "For example, `[1, 4]` and `[4, 6]` merge because they share endpoint 4."
        ),
        "starter_code": (
            "def solve(intervals):\n"
            "    # Sort by start, then extend or append each interval.\n"
            "    pass\n"
        ),
        "test_cases": [
            _case([[[1, 3], [2, 6], [8, 10], [15, 18]]], [[1, 6], [8, 10], [15, 18]]),
            _case([[[1, 4], [4, 5]]], [[1, 5]]),
            _case([[]], []),
        ],
    },
    {
        "id": "arrays_spiral_matrix",
        "competency_id": "arrays",
        "topic_label": "Matrices",
        "difficulty": "medium",
        "title": "Spiral Matrix Walk",
        "param_names": ["matrix"],
        "arg_types": ["int[][]"],
        "return_type": "int[]",
        "prompt": (
            "Return all values of a rectangular `matrix` in clockwise spiral order: traverse the "
            "top row, right edge, bottom row in reverse, and left edge in reverse, then repeat "
            "for the remaining inner rectangle."
        ),
        "starter_code": (
            "def solve(matrix):\n"
            "    # Shrink top, right, bottom and left boundaries after each pass.\n"
            "    pass\n"
        ),
        "test_cases": [
            _case([[[1, 2, 3], [4, 5, 6], [7, 8, 9]]], [1, 2, 3, 6, 9, 8, 7, 4, 5]),
            _case([[[1, 2, 3, 4], [5, 6, 7, 8]]], [1, 2, 3, 4, 8, 7, 6, 5]),
            _case([[]], []),
        ],
    },
    {
        "id": "arrays_prefix_sum_queries",
        "competency_id": "arrays",
        "topic_label": "Prefix Sums",
        "difficulty": "medium",
        "title": "Batch Range Sums",
        "param_names": ["nums", "queries"],
        "arg_types": ["int[]", "int[][]"],
        "return_type": "int[]",
        "prompt": (
            "For every inclusive query `[left, right]`, return the sum of `nums[left:right+1]`. "
            "Build one prefix-sum array so each query is answered in O(1) time after O(n) "
            "preprocessing. Return answers in the same order as the queries."
        ),
        "starter_code": (
            "def solve(nums, queries):\n"
            "    # prefix[i] stores the sum of nums before index i.\n"
            "    pass\n"
        ),
        "test_cases": [
            _case([[2, 4, 6, 8, 10], [[0, 2], [1, 3], [4, 4]]], [12, 18, 10]),
            _case([[-2, 5, -1, 3], [[0, 3], [1, 2]]], [5, 4]),
            _case([[7], [[0, 0]]], [7]),
        ],
    },
    {
        "id": "graphs_connected_components",
        "competency_id": "graphs",
        "topic_label": "Graph Traversal",
        "difficulty": "medium",
        "title": "Count Network Groups",
        "param_names": ["node_count", "edges"],
        "arg_types": ["int", "int[][]"],
        "return_type": "int",
        "prompt": (
            "An undirected graph has nodes `0` through `node_count - 1` and an edge list where "
            "each pair `[a, b]` joins two nodes. Return the number of connected components, "
            "including isolated nodes. DFS, BFS, or disjoint-set union are all valid."
        ),
        "starter_code": (
            "def solve(node_count, edges):\n"
            "    # Count connected groups; isolated nodes count as groups too.\n"
            "    pass\n"
        ),
        "test_cases": [
            _case([5, [[0, 1], [1, 2], [3, 4]]], 2),
            _case([4, []], 4),
            _case([6, [[0, 1], [1, 2], [2, 3], [3, 4], [4, 5]]], 1),
        ],
    },
]

PROBLEM_GUIDANCE = {
    "arrays_pair_sum_indices": {
        "constraints": ["2 <= len(nums) <= 10,000", "Exactly one valid pair exists", "Do not reuse one index"],
        "explanations": [
            "nums[0] + nums[1] is 2 + 7 = 9, so the answer is [0, 1].",
            "The values 2 and 4 occur at indices 1 and 2 and add to 6.",
        ],
        "solution_outline": "Scan once while storing value -> index in a hash map. For each value, look for target - value before storing the current index. Time O(n), space O(n).",
    },
    "linked_lists_middle_value": {
        "constraints": ["1 <= len(values) <= 10,000", "Return the second middle for even length"],
        "explanations": [
            "The slow pointer reaches 3 when the fast pointer reaches the end.",
            "With six nodes, slow advances to the second middle value, 4.",
        ],
        "solution_outline": "Advance slow by one position and fast by two. When fast cannot advance, slow is at the required middle. Time O(n), space O(1).",
    },
    "stacks_queues_balanced_brackets": {
        "constraints": ["0 <= len(s) <= 20,000", "s contains only ()[]{}"],
        "explanations": [
            "Each opening bracket is closed by the matching type in valid stack order.",
            "The closing ] does not match the most recent opening (, so the string is invalid.",
        ],
        "solution_outline": "Push opening brackets. For each closing bracket, pop and compare with its expected opener; the stack must be empty at the end. Time O(n).",
    },
    "binary_search_find_index": {
        "constraints": ["nums is sorted with distinct values", "Target may be absent", "Expected time O(log n)"],
        "explanations": [
            "Binary search discards the left half twice and finds 7 at index 3.",
            "The search interval becomes empty without seeing 4, so return -1.",
        ],
        "solution_outline": "Maintain inclusive low/high bounds. Compare the middle value and discard the half that cannot contain target. Time O(log n), space O(1).",
    },
    "recursion_count_ways_to_climb": {
        "constraints": ["1 <= n <= 40", "Each move is exactly 1 or 2 steps"],
        "explanations": [
            "The counts follow ways(4) = ways(3) + ways(2) = 3 + 2 = 5.",
            "ways(5) = ways(4) + ways(3) = 5 + 3 = 8.",
        ],
        "solution_outline": "Use ways(n)=ways(n-1)+ways(n-2) with base cases ways(1)=1 and ways(2)=2. Memoization makes it O(n).",
    },
    "trees_level_order_sum": {
        "constraints": ["level_order uses null for missing children", "level_index is zero-based", "At least one node exists"],
        "explanations": [
            "Level 2 contains nodes 15 and 7, whose sum is 22.",
            "Level 1 contains nodes 2 and 3, whose sum is 5.",
        ],
        "solution_outline": "Rebuild or traverse the level-order representation with a queue, tracking each node's depth and summing values at the requested level. Time O(n).",
    },
    "binary_search_tree_validate": {
        "constraints": ["All BST comparisons are strict", "The array uses level-order null markers", "Duplicate values invalidate a BST"],
        "explanations": [
            "Every node stays within the lower and upper bounds inherited from its ancestors.",
            "Node 6 appears in the right subtree of 10 but is below 10, violating the ancestor bound.",
        ],
        "solution_outline": "Traverse nodes with an allowed (low, high) range. A node must satisfy low < value < high, then narrows the range for its children. Time O(n).",
    },
    "heaps_kth_largest": {
        "constraints": ["1 <= k <= len(nums)", "Values may repeat", "Do not assume nums is sorted"],
        "explanations": [
            "In descending order the values begin 6, 5, so the second largest is 5.",
            "Counting duplicates, the descending sequence starts 6, 5, 5, 4; the fourth is 4.",
        ],
        "solution_outline": "Maintain a min-heap of the k largest values seen. Remove the smallest whenever size exceeds k; the heap root is the answer. Time O(n log k).",
    },
    "graphs_shortest_path_length": {
        "constraints": ["Graph is unweighted and undirected", "Nodes are valid adjacency indices", "Return -1 when unreachable"],
        "explanations": [
            "BFS reaches node 3 in two edges through either 0-1-3 or 0-2-3.",
            "The only path is 0-1-2, which uses two edges.",
        ],
        "solution_outline": "Run BFS from start, storing distance when each node is first visited. The first visit to end is the shortest path. Time O(V+E).",
    },
    "dynamic_programming_max_non_adjacent_sum": {
        "constraints": ["0 <= len(nums) <= 10,000", "All values are non-negative", "Chosen indices cannot be adjacent"],
        "explanations": [
            "Choose 2, 9 and 1 for 12; selecting 7 would block both neighboring choices.",
            "Choose the two 5s at the ends for a total of 10.",
        ],
        "solution_outline": "Track the best total including or excluding each position, or keep two rolling values. Time O(n), space O(1).",
    },
    "sorting_algorithms_kth_smallest": {
        "constraints": ["1 <= k <= len(nums)", "Values may repeat", "k is one-based"],
        "explanations": [
            "Sorting gives [1,2,3,5,8,9], so the third value is 3.",
            "All three values are 7, so the second smallest is also 7.",
        ],
        "solution_outline": "Sort ascending and return nums[k-1]. This direct exercise costs O(n log n); heap or selection approaches can improve some cases.",
    },
    "arrays_move_zeroes": {
        "constraints": ["0 <= len(nums) <= 10,000", "Preserve non-zero relative order"],
        "explanations": [
            "The non-zero sequence is [1,3,12]; append two zeroes to obtain the result.",
            "One non-zero value remains first, followed by the two zeroes.",
        ],
        "solution_outline": "Collect or compact non-zero values with a write pointer, then fill the remaining positions with zeroes. Time O(n).",
    },
    "graphs_has_cycle": {
        "constraints": ["Graph is directed", "Every neighbor is a valid node index", "Disconnected components are possible"],
        "explanations": [
            "The directed edges form 0 -> 1 -> 2 -> 0, returning to an active node.",
            "The chain 0 -> 1 -> 2 ends, so no cycle exists.",
        ],
        "solution_outline": "DFS with three states: unseen, active, finished. An edge to an active node proves a cycle. Time O(V+E).",
    },
    "dynamic_programming_longest_increasing_subsequence": {
        "constraints": ["1 <= len(nums) <= 10,000", "The subsequence need not be contiguous", "Values must increase strictly"],
        "explanations": [
            "One longest subsequence is [2,3,7,101], so the length is 4.",
            "A valid length-four subsequence is [0,1,2,3].",
        ],
        "solution_outline": "Maintain the smallest possible tail for each subsequence length and place each value with binary search. Time O(n log n).",
    },
    "strings_longest_unique_window": {
        "constraints": ["0 <= len(text) <= 50,000", "Characters are compared exactly", "Substring means contiguous"],
        "explanations": [
            "The windows 'abc', 'bca', and 'cab' have no repeats; none can grow past length 3.",
            "Every window longer than one repeats b, so the answer is 1.",
        ],
        "solution_outline": "Track the last index of each character and move the left boundary past repeats. Each index moves once: O(n) time, O(k) space.",
    },
    "hashing_first_unique_value": {
        "constraints": ["1 <= len(nums) <= 50,000", "Return the value, not its index", "Return -1 if none is unique"],
        "explanations": [
            "4, 1 and 2 repeat; 5 appears once and is encountered first.",
            "Both 7 and 8 occur twice, so no unique value exists.",
        ],
        "solution_outline": "Count frequencies in one pass, then scan the original list and return the first value with count one. Time O(n), space O(n).",
    },
    "two_pointers_sorted_squares": {
        "constraints": ["nums is sorted ascending", "0 <= len(nums) <= 50,000", "Return ascending squares"],
        "explanations": [
            "The largest absolute values are chosen from the ends: 10, -4, 3, -1, 0; fill output backwards.",
            "Comparing both ends produces squares 121, 49, 9, 9, 4 from right to left.",
        ],
        "solution_outline": "Compare absolute values at both ends, write the larger square into the result from right to left, and move that pointer. O(n) time.",
    },
    "backtracking_ordered_subsets": {
        "constraints": ["0 <= len(nums) <= 12", "All values are distinct", "Use exclude-then-include DFS order"],
        "explanations": [
            "Exclude 1 and 2 -> []; include only 2 -> [2]; include only 1 -> [1]; include both -> [1,2].",
            "The two branches are excluding 3 for [] and including 3 for [3].",
        ],
        "solution_outline": "At index i, recurse without nums[i], then append it and recurse again. Copy the current subset at the base case. O(n*2^n) output work.",
    },
    "sorting_merge_intervals": {
        "constraints": ["Each interval has start <= end", "Intervals may overlap or touch", "Return intervals sorted by start"],
        "explanations": [
            "[1,3] overlaps [2,6], forming [1,6]; the other intervals stay separate.",
            "The intervals share endpoint 4, so their union is [1,5].",
        ],
        "solution_outline": "Sort by start. Extend the last merged interval when the next start is <= its end; otherwise append a new interval. O(n log n).",
    },
    "arrays_spiral_matrix": {
        "constraints": ["Matrix is rectangular", "0 <= rows, columns <= 100", "Visit every cell exactly once"],
        "explanations": [
            "Walk the outside ring 1,2,3,6,9,8,7,4, then the center 5.",
            "Walk the top row 1,2,3,4, then the right and bottom edges 8,7,6,5.",
        ],
        "solution_outline": "Maintain top, bottom, left and right boundaries. Traverse each valid edge and shrink its boundary until they cross. O(rows*cols).",
    },
    "arrays_prefix_sum_queries": {
        "constraints": ["Every query satisfies 0 <= left <= right < len(nums)", "Return one answer per query", "Values may be negative"],
        "explanations": [
            "The ranges sum to 2+4+6=12, 4+6+8=18, and 10 respectively.",
            "The complete range sums to 5; indices 1 through 2 sum to 4.",
        ],
        "solution_outline": "Build prefix with prefix[i+1]=prefix[i]+nums[i]. Each inclusive range is prefix[right+1]-prefix[left]. O(n+q).",
    },
    "graphs_connected_components": {
        "constraints": ["0 <= node_count <= 10,000", "Graph is undirected", "Isolated nodes count as components"],
        "explanations": [
            "Nodes {0,1,2} form one group and {3,4} form another, giving 2.",
            "With no edges, each of the four nodes is its own component.",
        ],
        "solution_outline": "Build adjacency lists and start DFS/BFS from every unvisited node, incrementing the component count each time. O(V+E).",
    },
}

PROBLEMS_BY_ID = {problem["id"]: problem for problem in PROBLEMS}


def public_problem(problem: dict) -> dict:
    """Return two worked examples while keeping hidden judge cases private."""
    guidance = PROBLEM_GUIDANCE[problem["id"]]
    examples = [
        {
            "input": test_case["args"],
            "output": json.loads(test_case["expected_output"]),
            "explanation": guidance["explanations"][index],
        }
        for index, test_case in enumerate(problem["test_cases"][:2])
    ]
    return {
        "id": problem["id"],
        "competency_id": problem["competency_id"],
        "topic_label": problem["topic_label"],
        "difficulty": problem["difficulty"],
        "title": problem["title"],
        "prompt": problem["prompt"],
        "starter_code": problem["starter_code"],
        "starter_code_by_language": {
            lang: dsa_lang_gen.starter_code(lang, problem) for lang in dsa_lang_gen.LANGUAGES
        },
        "test_case_count": len(problem["test_cases"]),
        "sample_input": problem["test_cases"][0]["args"],
        "constraints": guidance["constraints"],
        "examples": examples,
        "solution_outline": guidance["solution_outline"],
    }
