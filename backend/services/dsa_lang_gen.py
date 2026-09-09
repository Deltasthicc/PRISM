"""Per-language starter code and judge harness generation for the DSA
sandbox (services/dsa_problems.py, routes/dsa_sandbox.py).

Every problem's `solve` signature is fully described by a short list of
argument type tags (see ARG_TYPES below) plus a return type tag. Python and
JavaScript are dynamically typed and only need ONE constant harness each
(they parse the bare-JSON-array stdin and call `solve(*args)` /
`solve(...args)` generically) -- see PY_HARNESS / JS_HARNESS.

Java, C++ and C# are statically typed and Judge0 has no JSON library
available on any of them (confirmed empirically: Mono 6.6's
System.Text.Json is absent, and neither the plain JDK nor g++ ships one).
So each of those three languages carries a small, hand-verified minimal
JSON parser (MINI_JSON_*), and this module generates, per problem, the
handful of lines that extract typed arguments from the parsed generic JSON
tree and call the learner's `solve`. The extraction/wrap logic is
data-driven from ARG_TYPES so it is written once per type tag, not once per
problem.

Every one of these harnesses has been validated against the real Judge0 CE
API (https://ce.judge0.com) for at least one problem per language before
being wired into the sandbox -- see PR description / commit history for the
verification transcript.
"""

# Judge0 language IDs, confirmed live against https://ce.judge0.com/languages
LANGUAGES = {
    "python": {"judge0_id": 71, "label": "Python 3 (3.8.1)"},
    "javascript": {"judge0_id": 102, "label": "JavaScript (Node.js 22.08.0)"},
    "java": {"judge0_id": 91, "label": "Java (JDK 17.0.6)"},
    "cpp": {"judge0_id": 105, "label": "C++ (GCC 14.1.0)"},
    "csharp": {"judge0_id": 51, "label": "C# (Mono 6.6.0.161)"},
}

DEFAULT_LANGUAGE = "python"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _comment_lines(problem: dict) -> list:
    """Pull the `# ...` guidance lines out of the existing Python
    starter_code so every language's stub carries the same, already-authored
    guidance instead of re-writing it once per language."""
    lines = []
    for line in problem["starter_code"].splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            lines.append(stripped[1:].strip())
    return lines


# ---------------------------------------------------------------------------
# Python (existing behaviour, wire protocol simplified to a bare JSON array)
# ---------------------------------------------------------------------------

PY_HARNESS = (
    "\n\nimport sys, json\n"
    "_args = json.loads(sys.stdin.read())\n"
    "print(json.dumps(solve(*_args), separators=(',', ':')))\n"
)


def python_starter(problem: dict) -> str:
    return problem["starter_code"]


# ---------------------------------------------------------------------------
# JavaScript -- also fully generic, no per-type marshalling needed
# ---------------------------------------------------------------------------

JS_HARNESS = (
    "\n\nconst _args = JSON.parse(require('fs').readFileSync(0, 'utf-8'));\n"
    "console.log(JSON.stringify(solve(..._args)));\n"
)


def javascript_starter(problem: dict) -> str:
    params = ", ".join(problem["param_names"])
    lines = [f"function solve({params}) {{"]
    for c in _comment_lines(problem):
        lines.append(f"    // {c}")
    lines.append("}")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Java
# ---------------------------------------------------------------------------

_JAVA_FRIENDLY_TYPE = {
    "int": "long",
    "str": "String",
    "bool": "boolean",
    "int[]": "List<Long>",
    "nullable_int[]": "List<Long>",
    "int[][]": "List<List<Long>>",
}
_JAVA_DEFAULT_RETURN = {
    "int": "0",
    "str": "null",
    "bool": "false",
    "int[]": "null",
    "nullable_int[]": "null",
    "int[][]": "null",
}
_JAVA_EXTRACT_FN = {
    "int": "__extractLong",
    "str": "__extractStr",
    "bool": "__extractBool",
    "int[]": "__extractLongList",
    "nullable_int[]": "__extractNullableLongList",
    "int[][]": "__extractLongMatrix",
}

MINI_JSON_JAVA = """
class MiniJson {
    private final String s;
    private int i;
    private MiniJson(String s) { this.s = s; this.i = 0; }

    static Object parse(String s) {
        MiniJson p = new MiniJson(s);
        p.skipWs();
        return p.parseValue();
    }

    private void skipWs() { while (i < s.length() && Character.isWhitespace(s.charAt(i))) i++; }

    private Object parseValue() {
        skipWs();
        char c = s.charAt(i);
        if (c == '[') return parseArray();
        if (c == '"') return parseString();
        if (c == 't') { i += 4; return Boolean.TRUE; }
        if (c == 'f') { i += 5; return Boolean.FALSE; }
        if (c == 'n') { i += 4; return null; }
        return parseNumber();
    }

    private java.util.List<Object> parseArray() {
        java.util.List<Object> out = new java.util.ArrayList<>();
        i++;
        skipWs();
        if (s.charAt(i) == ']') { i++; return out; }
        while (true) {
            out.add(parseValue());
            skipWs();
            if (s.charAt(i) == ',') { i++; continue; }
            if (s.charAt(i) == ']') { i++; break; }
        }
        return out;
    }

    private String parseString() {
        i++;
        StringBuilder sb = new StringBuilder();
        while (s.charAt(i) != '"') {
            if (s.charAt(i) == '\\\\') { i++; sb.append(s.charAt(i)); i++; }
            else { sb.append(s.charAt(i)); i++; }
        }
        i++;
        return sb.toString();
    }

    private Long parseNumber() {
        int start = i;
        if (s.charAt(i) == '-') i++;
        while (i < s.length() && Character.isDigit(s.charAt(i))) i++;
        return Long.parseLong(s.substring(start, i));
    }

    static String stringify(Object v) {
        if (v == null) return "null";
        if (v instanceof Boolean) return v.toString();
        if (v instanceof Number) return String.valueOf(((Number) v).longValue());
        if (v instanceof String) return "\\"" + v + "\\"";
        if (v instanceof java.util.List) {
            StringBuilder sb = new StringBuilder("[");
            java.util.List<?> list = (java.util.List<?>) v;
            for (int j = 0; j < list.size(); j++) {
                if (j > 0) sb.append(",");
                sb.append(stringify(list.get(j)));
            }
            sb.append("]");
            return sb.toString();
        }
        throw new RuntimeException("cannot stringify: " + v);
    }
}
"""

JAVA_DRIVER_HELPERS = """
class Main {
    static long __extractLong(Object o) { return ((Number) o).longValue(); }
    static String __extractStr(Object o) { return (String) o; }
    static boolean __extractBool(Object o) { return ((Boolean) o).booleanValue(); }

    @SuppressWarnings("unchecked")
    static java.util.List<Long> __extractLongList(Object o) {
        java.util.List<Object> raw = (java.util.List<Object>) o;
        java.util.List<Long> out = new java.util.ArrayList<>();
        for (Object e : raw) out.add(((Number) e).longValue());
        return out;
    }

    @SuppressWarnings("unchecked")
    static java.util.List<Long> __extractNullableLongList(Object o) {
        java.util.List<Object> raw = (java.util.List<Object>) o;
        java.util.List<Long> out = new java.util.ArrayList<>();
        for (Object e : raw) out.add(e == null ? null : ((Number) e).longValue());
        return out;
    }

    @SuppressWarnings("unchecked")
    static java.util.List<java.util.List<Long>> __extractLongMatrix(Object o) {
        java.util.List<Object> raw = (java.util.List<Object>) o;
        java.util.List<java.util.List<Long>> out = new java.util.ArrayList<>();
        for (Object e : raw) out.add(__extractLongList(e));
        return out;
    }

    @SuppressWarnings("unchecked")
    public static void main(String[] args) throws Exception {
        java.util.Scanner __scanner = new java.util.Scanner(System.in);
        StringBuilder __sb = new StringBuilder();
        while (__scanner.hasNextLine()) __sb.append(__scanner.nextLine());
        java.util.List<Object> __args = (java.util.List<Object>) MiniJson.parse(__sb.toString());
%(extract_lines)s
        Object __result = Solution.solve(%(call_args)s);
        System.out.println(MiniJson.stringify(__result));
    }
}
"""


def java_starter(problem: dict) -> str:
    params = ", ".join(
        f"{_JAVA_FRIENDLY_TYPE[t]} {n}"
        for t, n in zip(problem["arg_types"], problem["param_names"])
    )
    ret = _JAVA_FRIENDLY_TYPE[problem["return_type"]]
    default_ret = _JAVA_DEFAULT_RETURN[problem["return_type"]]
    lines = [
        "import java.util.*;",
        "",
        "class Solution {",
        f"    static {ret} solve({params}) {{",
    ]
    for c in _comment_lines(problem):
        lines.append(f"        // {c}")
    lines.append(f"        return {default_ret};")
    lines.append("    }")
    lines.append("}")
    return "\n".join(lines) + "\n"


def java_harness(problem: dict) -> str:
    extract_lines = []
    call_args = []
    for idx, (tag, name) in enumerate(zip(problem["arg_types"], problem["param_names"])):
        fn = _JAVA_EXTRACT_FN[tag]
        java_type = _JAVA_FRIENDLY_TYPE[tag]
        extract_lines.append(f"        {java_type} {name} = {fn}(__args.get({idx}));")
        call_args.append(name)
    body = JAVA_DRIVER_HELPERS % {
        "extract_lines": "\n".join(extract_lines),
        "call_args": ", ".join(call_args),
    }
    return "\n\n" + MINI_JSON_JAVA + body


# ---------------------------------------------------------------------------
# C++
# ---------------------------------------------------------------------------

_CPP_FRIENDLY_TYPE = {
    "int": "long long",
    "str": "string",
    "bool": "bool",
    "int[]": "vector<long long>",
    "nullable_int[]": "vector<optional<long long>>",
    "int[][]": "vector<vector<long long>>",
}
_CPP_DEFAULT_RETURN = {
    "int": "0",
    "str": '""',
    "bool": "false",
    "int[]": "{}",
    "nullable_int[]": "{}",
    "int[][]": "{}",
}
_CPP_EXTRACT_FN = {
    "int": "__extractInt",
    "str": "__extractStr",
    "bool": "__extractBool",
    "int[]": "__extractIntArr",
    "nullable_int[]": "__extractNullableIntArr",
    "int[][]": "__extractIntMatrix",
}

MINI_JSON_CPP = """
struct JsonValue {
    enum Type { NUL, BOOL, NUM, STR, ARR } type;
    bool b = false;
    long long num = 0;
    string str;
    vector<JsonValue> arr;

    static JsonValue mkNull() { JsonValue v; v.type = NUL; return v; }
    static JsonValue mkBool(bool x) { JsonValue v; v.type = BOOL; v.b = x; return v; }
    static JsonValue mkNum(long long x) { JsonValue v; v.type = NUM; v.num = x; return v; }
    static JsonValue mkStr(const string& x) { JsonValue v; v.type = STR; v.str = x; return v; }
    static JsonValue mkArr(const vector<JsonValue>& x) { JsonValue v; v.type = ARR; v.arr = x; return v; }
};

struct JsonParser {
    const string& s;
    size_t i = 0;
    JsonParser(const string& s) : s(s) {}

    void skipWs() { while (i < s.size() && isspace((unsigned char)s[i])) i++; }

    JsonValue parseValue() {
        skipWs();
        char c = s[i];
        if (c == '[') return parseArray();
        if (c == '"') return JsonValue::mkStr(parseString());
        if (c == 't') { i += 4; return JsonValue::mkBool(true); }
        if (c == 'f') { i += 5; return JsonValue::mkBool(false); }
        if (c == 'n') { i += 4; return JsonValue::mkNull(); }
        return parseNumber();
    }

    JsonValue parseArray() {
        vector<JsonValue> out;
        i++;
        skipWs();
        if (s[i] == ']') { i++; return JsonValue::mkArr(out); }
        while (true) {
            out.push_back(parseValue());
            skipWs();
            if (s[i] == ',') { i++; continue; }
            if (s[i] == ']') { i++; break; }
        }
        return JsonValue::mkArr(out);
    }

    string parseString() {
        i++;
        string out;
        while (s[i] != '"') {
            if (s[i] == '\\\\') { i++; out += s[i]; i++; }
            else { out += s[i]; i++; }
        }
        i++;
        return out;
    }

    JsonValue parseNumber() {
        size_t start = i;
        if (s[i] == '-') i++;
        while (i < s.size() && isdigit((unsigned char)s[i])) i++;
        return JsonValue::mkNum(stoll(s.substr(start, i - start)));
    }
};

JsonValue __parseJson(const string& s) {
    JsonParser p(s);
    return p.parseValue();
}

string __stringifyJson(const JsonValue& v) {
    switch (v.type) {
        case JsonValue::NUL: return "null";
        case JsonValue::BOOL: return v.b ? "true" : "false";
        case JsonValue::NUM: return to_string(v.num);
        case JsonValue::STR: return "\\"" + v.str + "\\"";
        case JsonValue::ARR: {
            string out = "[";
            for (size_t j = 0; j < v.arr.size(); j++) {
                if (j > 0) out += ",";
                out += __stringifyJson(v.arr[j]);
            }
            out += "]";
            return out;
        }
    }
    return "null";
}

long long __extractInt(const JsonValue& v) { return v.num; }
string __extractStr(const JsonValue& v) { return v.str; }
bool __extractBool(const JsonValue& v) { return v.b; }
vector<long long> __extractIntArr(const JsonValue& v) {
    vector<long long> out;
    for (auto& e : v.arr) out.push_back(e.num);
    return out;
}
vector<vector<long long>> __extractIntMatrix(const JsonValue& v) {
    vector<vector<long long>> out;
    for (auto& e : v.arr) out.push_back(__extractIntArr(e));
    return out;
}
vector<optional<long long>> __extractNullableIntArr(const JsonValue& v) {
    vector<optional<long long>> out;
    for (auto& e : v.arr) out.push_back(e.type == JsonValue::NUL ? nullopt : optional<long long>(e.num));
    return out;
}

JsonValue __wrap(long long x) { return JsonValue::mkNum(x); }
JsonValue __wrap(bool x) { return JsonValue::mkBool(x); }
JsonValue __wrap(const string& x) { return JsonValue::mkStr(x); }
JsonValue __wrap(const vector<long long>& v) {
    vector<JsonValue> a;
    for (auto x : v) a.push_back(JsonValue::mkNum(x));
    return JsonValue::mkArr(a);
}
"""

CPP_MAIN_TEMPLATE = """
int main() {
    string __input, __line;
    while (getline(cin, __line)) __input += __line;
    JsonValue __parsed = __parseJson(__input);
%(extract_lines)s
    auto __result = solve(%(call_args)s);
    cout << __stringifyJson(__wrap(__result)) << endl;
    return 0;
}
"""


def cpp_starter(problem: dict) -> str:
    params = ", ".join(
        f"{_CPP_FRIENDLY_TYPE[t]} {n}"
        for t, n in zip(problem["arg_types"], problem["param_names"])
    )
    ret = _CPP_FRIENDLY_TYPE[problem["return_type"]]
    default_ret = _CPP_DEFAULT_RETURN[problem["return_type"]]
    lines = [
        "#include <bits/stdc++.h>",
        "using namespace std;",
        "",
        f"{ret} solve({params}) {{",
    ]
    for c in _comment_lines(problem):
        lines.append(f"    // {c}")
    lines.append(f"    return {default_ret};")
    lines.append("}")
    return "\n".join(lines) + "\n"


def cpp_harness(problem: dict) -> str:
    extract_lines = []
    call_args = []
    for idx, (tag, name) in enumerate(zip(problem["arg_types"], problem["param_names"])):
        fn = _CPP_EXTRACT_FN[tag]
        cpp_type = _CPP_FRIENDLY_TYPE[tag]
        extract_lines.append(f"    {cpp_type} {name} = {fn}(__parsed.arr[{idx}]);")
        call_args.append(name)
    body = CPP_MAIN_TEMPLATE % {
        "extract_lines": "\n".join(extract_lines),
        "call_args": ", ".join(call_args),
    }
    return "\n\n" + MINI_JSON_CPP + body


# ---------------------------------------------------------------------------
# C#
# ---------------------------------------------------------------------------

_CS_FRIENDLY_TYPE = {
    "int": "long",
    "str": "string",
    "bool": "bool",
    "int[]": "List<long>",
    "nullable_int[]": "List<long?>",
    "int[][]": "List<List<long>>",
}
_CS_DEFAULT_RETURN = {
    "int": "0",
    "str": "null",
    "bool": "false",
    "int[]": "null",
    "nullable_int[]": "null",
    "int[][]": "null",
}
_CS_EXTRACT_FN = {
    "int": "__extractLong",
    "str": "__extractStr",
    "bool": "__extractBool",
    "int[]": "__extractLongList",
    "nullable_int[]": "__extractNullableLongList",
    "int[][]": "__extractLongMatrix",
}

MINI_JSON_CS = """
class MiniJson {
    string s; int i;
    MiniJson(string s) { this.s = s; this.i = 0; }

    public static object Parse(string s) {
        var p = new MiniJson(s);
        p.SkipWs();
        return p.ParseValue();
    }

    void SkipWs() { while (i < s.Length && char.IsWhiteSpace(s[i])) i++; }

    object ParseValue() {
        SkipWs();
        char c = s[i];
        if (c == '[') return ParseArray();
        if (c == '"') return ParseString();
        if (c == 't') { i += 4; return true; }
        if (c == 'f') { i += 5; return false; }
        if (c == 'n') { i += 4; return null; }
        return ParseNumber();
    }

    System.Collections.Generic.List<object> ParseArray() {
        var outList = new System.Collections.Generic.List<object>();
        i++;
        SkipWs();
        if (s[i] == ']') { i++; return outList; }
        while (true) {
            outList.Add(ParseValue());
            SkipWs();
            if (s[i] == ',') { i++; continue; }
            if (s[i] == ']') { i++; break; }
        }
        return outList;
    }

    string ParseString() {
        i++;
        var sb = new System.Text.StringBuilder();
        while (s[i] != '"') {
            if (s[i] == 92) { i++; sb.Append(s[i]); i++; }
            else { sb.Append(s[i]); i++; }
        }
        i++;
        return sb.ToString();
    }

    long ParseNumber() {
        int start = i;
        if (s[i] == '-') i++;
        while (i < s.Length && char.IsDigit(s[i])) i++;
        return long.Parse(s.Substring(start, i - start));
    }

    public static string Stringify(object v) {
        if (v == null) return "null";
        if (v is bool) return ((bool)v) ? "true" : "false";
        if (v is long) return v.ToString();
        if (v is int) return v.ToString();
        if (v is string) return "\\"" + (string)v + "\\"";
        if (v is System.Collections.Generic.List<object>) {
            var list = (System.Collections.Generic.List<object>)v;
            var sb = new System.Text.StringBuilder("[");
            for (int j = 0; j < list.Count; j++) {
                if (j > 0) sb.Append(",");
                sb.Append(Stringify(list[j]));
            }
            sb.Append("]");
            return sb.ToString();
        }
        throw new System.Exception("cannot stringify");
    }
}
"""

CS_PROGRAM_TEMPLATE = """
class Program {
    static long __extractLong(object o) { return (long)o; }
    static string __extractStr(object o) { return (string)o; }
    static bool __extractBool(object o) { return (bool)o; }

    static System.Collections.Generic.List<long> __extractLongList(object o) {
        var raw = (System.Collections.Generic.List<object>)o;
        var outp = new System.Collections.Generic.List<long>();
        foreach (var e in raw) outp.Add((long)e);
        return outp;
    }

    static System.Collections.Generic.List<long?> __extractNullableLongList(object o) {
        var raw = (System.Collections.Generic.List<object>)o;
        var outp = new System.Collections.Generic.List<long?>();
        foreach (var e in raw) outp.Add(e == null ? (long?)null : (long)e);
        return outp;
    }

    static System.Collections.Generic.List<System.Collections.Generic.List<long>> __extractLongMatrix(object o) {
        var raw = (System.Collections.Generic.List<object>)o;
        var outp = new System.Collections.Generic.List<System.Collections.Generic.List<long>>();
        foreach (var e in raw) outp.Add(__extractLongList(e));
        return outp;
    }

    static object __wrap(long x) { return x; }
    static object __wrap(bool x) { return x; }
    static object __wrap(string x) { return x; }
    static object __wrap(System.Collections.Generic.List<long> v) {
        var outp = new System.Collections.Generic.List<object>();
        foreach (var x in v) outp.Add(x);
        return outp;
    }
    static object __wrap(System.Collections.Generic.List<long?> v) {
        var outp = new System.Collections.Generic.List<object>();
        foreach (var x in v) outp.Add(x.HasValue ? (object)x.Value : null);
        return outp;
    }

    static void Main() {
        string __input = System.Console.In.ReadToEnd();
        var __args = (System.Collections.Generic.List<object>)MiniJson.Parse(__input);
%(extract_lines)s
        var __result = Solution.Solve(%(call_args)s);
        System.Console.WriteLine(MiniJson.Stringify(__wrap(__result)));
    }
}
"""


def csharp_starter(problem: dict) -> str:
    params = ", ".join(
        f"{_CS_FRIENDLY_TYPE[t]} {n}"
        for t, n in zip(problem["arg_types"], problem["param_names"])
    )
    ret = _CS_FRIENDLY_TYPE[problem["return_type"]]
    default_ret = _CS_DEFAULT_RETURN[problem["return_type"]]
    lines = [
        "using System;",
        "using System.Collections.Generic;",
        "using System.Linq;",
        "",
        "class Solution {",
        f"    public static {ret} Solve({params}) {{",
    ]
    for c in _comment_lines(problem):
        lines.append(f"        // {c}")
    lines.append(f"        return {default_ret};")
    lines.append("    }")
    lines.append("}")
    return "\n".join(lines) + "\n"


def csharp_harness(problem: dict) -> str:
    extract_lines = []
    call_args = []
    for idx, (tag, name) in enumerate(zip(problem["arg_types"], problem["param_names"])):
        fn = _CS_EXTRACT_FN[tag]
        cs_type = _CS_FRIENDLY_TYPE[tag]
        extract_lines.append(f"        {cs_type} {name} = {fn}(__args[{idx}]);")
        call_args.append(name)
    body = CS_PROGRAM_TEMPLATE % {
        "extract_lines": "\n".join(extract_lines),
        "call_args": ", ".join(call_args),
    }
    return "\n\n" + MINI_JSON_CS + body


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_STARTER_FNS = {
    "python": python_starter,
    "javascript": javascript_starter,
    "java": java_starter,
    "cpp": cpp_starter,
    "csharp": csharp_starter,
}

_HARNESS_FNS = {
    "python": lambda problem: PY_HARNESS,
    "javascript": lambda problem: JS_HARNESS,
    "java": java_harness,
    "cpp": cpp_harness,
    "csharp": csharp_harness,
}


def starter_code(language: str, problem: dict) -> str:
    return _STARTER_FNS[language](problem)


def build_harness(language: str, problem: dict) -> str:
    return _HARNESS_FNS[language](problem)


def full_source(language: str, learner_code: str, problem: dict) -> str:
    return learner_code + build_harness(language, problem)
