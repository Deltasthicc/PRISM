"""Data-driven curricula used by the game and the skill-intelligence layer.

Competency identifiers are globally unique because the current
``accuracy_history`` table is keyed by ``(player_id, topic)``. Keeping the
catalog in one module removes the old DSA-only knowledge-graph assumption
without pretending that this in-repository seed data is the authoritative
iGOT or Karmayogi Competency Model catalog.
"""

from copy import deepcopy


# SIH26101_TEAM_ORCHESTRATION.md section 5, Lane 3 acceptance evidence:
# "Every competency/target has source, authoring status and version." The
# per-curriculum `source` key below records origin; `authoring_status` records
# assurance using the fixed documented vocabulary (CODEX.md architectural
# invariants), and PROVISIONAL is the only honest value until a named domain
# reviewer validates this taxonomy -- SIH26101_MASTER_CHECKLIST.md section 4.1
# marks that BLOCKED-EXTERNAL.
PROVISIONAL = "PROVISIONAL"
COMPETENCY_VERSION = 1


CURRICULA = {
    "dsa-fundamentals": {
        "name": "DSA Fundamentals",
        "domain": "Data Structures & Algorithms",
        "description": "The original DSA practice path, from arrays through advanced graph and dynamic-programming concepts.",
        "audience": "Computer-science learners and software-engineering candidates",
        "level_band": "Beginner to advanced",
        "source": "core",
        "competencies": [
            {"id": "arrays", "label": "Arrays", "description": "Indexing, traversal, mutation, and complexity.", "prerequisites": [], "target_level": 2},
            {"id": "linked_lists", "label": "Linked Lists", "description": "Node-based storage and pointer operations.", "prerequisites": ["arrays"], "target_level": 2},
            {"id": "stacks_queues", "label": "Stacks & Queues", "description": "LIFO, FIFO, and common applications.", "prerequisites": ["arrays"], "target_level": 2},
            {"id": "binary_search", "label": "Binary Search", "description": "Search invariants and logarithmic reasoning.", "prerequisites": ["arrays"], "target_level": 3},
            {"id": "recursion", "label": "Recursion", "description": "Base cases, recursive structure, and call stacks.", "prerequisites": ["arrays"], "target_level": 3},
            {"id": "trees", "label": "Trees", "description": "Hierarchical structures and traversals.", "prerequisites": ["linked_lists", "recursion"], "target_level": 3},
            {"id": "binary_search_tree", "label": "Binary Search Trees", "description": "Ordered-tree search, insert, and delete.", "prerequisites": ["trees", "binary_search"], "target_level": 4},
            {"id": "heaps", "label": "Heaps", "description": "Priority queues and heap invariants.", "prerequisites": ["trees"], "target_level": 4},
            {"id": "graphs", "label": "Graphs", "description": "Graph representation, traversal, and paths.", "prerequisites": ["trees"], "target_level": 4},
            {"id": "dynamic_programming", "label": "Dynamic Programming", "description": "Overlapping subproblems and optimal substructure.", "prerequisites": ["recursion", "arrays"], "target_level": 5},
            {"id": "sorting_algorithms", "label": "Sorting Algorithms", "description": "Sorting strategies, trade-offs, and lower bounds.", "prerequisites": ["arrays", "recursion"], "target_level": 4},
        ],
    },
    "official-statistics": {
        "name": "Official Statistics & Data Governance",
        "domain": "Official Statistics",
        "description": "A MoSPI-aligned demonstration path covering the statistical production lifecycle and emerging data capabilities.",
        "audience": "Officials involved in data collection, analysis, dissemination, and policy support",
        "level_band": "Foundation to specialist",
        "source": "demo",
        "competencies": [
            {"id": "os_statistical_foundations", "label": "Statistical Foundations", "description": "Descriptive statistics, inference, uncertainty, and interpretation.", "prerequisites": [], "target_level": 3},
            {"id": "os_data_collection", "label": "Data Collection", "description": "Administrative data, surveys, instruments, and field operations.", "prerequisites": ["os_statistical_foundations"], "target_level": 3},
            {"id": "os_sampling_design", "label": "Sampling Design", "description": "Frames, probability samples, weights, and non-response.", "prerequisites": ["os_statistical_foundations", "os_data_collection"], "target_level": 4},
            {"id": "os_data_quality", "label": "Data Quality", "description": "Validation, metadata, revisions, and quality assurance.", "prerequisites": ["os_data_collection"], "target_level": 4},
            {"id": "os_official_statistics", "label": "Official Statistics", "description": "Principles, standards, statistical products, and dissemination.", "prerequisites": ["os_sampling_design", "os_data_quality"], "target_level": 4},
            {"id": "os_visualization", "label": "Data Visualisation", "description": "Clear, accessible, decision-oriented statistical communication.", "prerequisites": ["os_statistical_foundations"], "target_level": 3},
            {"id": "os_gis", "label": "GIS for Statistics", "description": "Spatial data, geographies, joins, and thematic mapping.", "prerequisites": ["os_data_quality", "os_visualization"], "target_level": 4},
            {"id": "os_big_data", "label": "Big Data & Cloud", "description": "Modern data pipelines, scale, governance, and cloud concepts.", "prerequisites": ["os_data_quality"], "target_level": 4},
            {"id": "os_ml", "label": "ML for Official Statistics", "description": "Responsible use of machine learning in statistical workflows.", "prerequisites": ["os_official_statistics", "os_big_data"], "target_level": 5},
            # PS-02 "Statistical" named scope (docs/SIH26101_PROBLEM_STATEMENT.md).
            # Traceability from each named item to these IDs lives in
            # services/ps02_coverage.py, which fails at import if one is dropped.
            {"id": "os_survey_design", "label": "Survey Design", "description": "Questionnaire design, modes, pilots, and respondent burden.", "prerequisites": ["os_data_collection"], "target_level": 4},
            {"id": "os_national_accounts", "label": "National Accounts", "description": "GDP aggregates, sectoral accounts, and SNA concepts.", "prerequisites": ["os_official_statistics"], "target_level": 4},
            {"id": "os_price_statistics", "label": "Price Statistics", "description": "CPI/WPI baskets, weights, index construction, and rebasing.", "prerequisites": ["os_official_statistics"], "target_level": 4},
            {"id": "os_labour_statistics", "label": "Labour Statistics", "description": "Employment, unemployment, participation, and workforce classification.", "prerequisites": ["os_official_statistics"], "target_level": 4},
            {"id": "os_agricultural_statistics", "label": "Agricultural Statistics", "description": "Crop estimation, area/yield surveys, and seasonal reporting.", "prerequisites": ["os_official_statistics"], "target_level": 4},
            {"id": "os_industrial_statistics", "label": "Industrial Statistics", "description": "Industrial production indices, enterprise surveys, and classifications.", "prerequisites": ["os_official_statistics"], "target_level": 4},
            {"id": "os_sdg_indicators", "label": "SDG Indicators", "description": "National indicator frameworks, tiers, disaggregation, and reporting.", "prerequisites": ["os_official_statistics"], "target_level": 4},
            {"id": "os_metadata_standards", "label": "Metadata Standards", "description": "Documentation, classifications, and exchange standards for statistical data.", "prerequisites": ["os_data_quality"], "target_level": 4},
            # PS-02 "Technical" named scope. GIS, Data Visualization, AI/ML and
            # Cloud Computing are already covered by os_gis, os_visualization,
            # os_ml and os_big_data respectively -- see ps02_coverage.py.
            {"id": "os_statistical_programming", "label": "Statistical Programming", "description": "Reproducible analysis in Python, R, Stata, SPSS, or SAS.", "prerequisites": ["os_statistical_foundations"], "target_level": 4},
            {"id": "os_data_management_sql", "label": "Data Management & SQL", "description": "Relational modelling, querying, joins, and data preparation.", "prerequisites": ["os_statistical_foundations"], "target_level": 3},
            {"id": "os_apis_interoperability", "label": "APIs & Interoperability", "description": "Consuming and publishing data through documented interfaces.", "prerequisites": ["os_data_management_sql"], "target_level": 3},
            {"id": "os_open_data", "label": "Open Data", "description": "Open formats, licensing, release policy, and public data portals.", "prerequisites": ["os_official_statistics", "os_metadata_standards"], "target_level": 3},
        ],
    },
    "public-policy": {
        "name": "Public Policy & Programme Evaluation",
        "domain": "Public Administration",
        "description": "Role-relevant learning for evidence-based programme design, delivery, and evaluation.",
        "audience": "Public administrators, programme managers, analysts, and policy professionals",
        "level_band": "Beginner to advanced",
        "source": "demo",
        "competencies": [
            {"id": "pa_governance_foundations", "label": "Governance Foundations", "description": "Institutions, accountability, ethics, and citizen orientation.", "prerequisites": [], "target_level": 2},
            {"id": "pa_policy_design", "label": "Policy Design", "description": "Problem framing, options, stakeholders, and theory of change.", "prerequisites": ["pa_governance_foundations"], "target_level": 3},
            {"id": "pa_public_finance", "label": "Public Finance", "description": "Budgets, expenditure, value for money, and fiscal trade-offs.", "prerequisites": ["pa_governance_foundations"], "target_level": 3},
            {"id": "pa_program_management", "label": "Programme Management", "description": "Delivery planning, risks, coordination, and implementation.", "prerequisites": ["pa_policy_design"], "target_level": 4},
            {"id": "pa_monitoring_evaluation", "label": "Monitoring & Evaluation", "description": "Indicators, baselines, targets, and learning loops.", "prerequisites": ["pa_policy_design", "pa_public_finance"], "target_level": 4},
            {"id": "pa_impact_evaluation", "label": "Impact Evaluation", "description": "Causal inference, experimental and quasi-experimental designs.", "prerequisites": ["pa_monitoring_evaluation"], "target_level": 5},
            {"id": "pa_data_storytelling", "label": "Evidence Communication", "description": "Communicating evidence clearly to decision-makers and citizens.", "prerequisites": ["pa_monitoring_evaluation"], "target_level": 4},
            # PS-02 "Behavioural and Managerial" named scope. Project Management
            # is covered by pa_program_management above; see ps02_coverage.py.
            {"id": "pa_leadership", "label": "Leadership", "description": "Setting direction, developing people, and leading through influence.", "prerequisites": ["pa_governance_foundations"], "target_level": 4},
            {"id": "pa_communication", "label": "Professional Communication", "description": "Written, verbal, and cross-team communication in an official setting.", "prerequisites": ["pa_governance_foundations"], "target_level": 3},
            {"id": "pa_ethics", "label": "Ethics & Integrity", "description": "Conflict of interest, confidentiality, and ethical judgment in public service.", "prerequisites": ["pa_governance_foundations"], "target_level": 4},
            {"id": "pa_decision_making", "label": "Decision Making", "description": "Structured decisions under uncertainty, trade-offs, and accountability.", "prerequisites": ["pa_policy_design"], "target_level": 4},
            {"id": "pa_change_management", "label": "Change Management", "description": "Leading adoption, managing resistance, and sustaining new ways of working.", "prerequisites": ["pa_program_management"], "target_level": 4},
        ],
    },
    "digital-literacy": {
        "name": "Digital & AI Literacy",
        "domain": "Digital Fluency",
        "description": "An accessible path for non-technical learners who need safe, practical digital and AI skills.",
        "audience": "Beginners, frontline staff, career switchers, and non-technical professionals",
        "level_band": "Absolute beginner to practitioner",
        "source": "demo",
        "competencies": [
            {"id": "dl_digital_foundations", "label": "Digital Foundations", "description": "Devices, files, browsers, accounts, and digital workflows.", "prerequisites": [], "target_level": 2},
            {"id": "dl_cyber_hygiene", "label": "Cyber Hygiene", "description": "Passwords, phishing, privacy, safe sharing, and incident reporting.", "prerequisites": ["dl_digital_foundations"], "target_level": 3},
            {"id": "dl_collaboration", "label": "Digital Collaboration", "description": "Documents, meetings, versioning, and responsible teamwork.", "prerequisites": ["dl_digital_foundations"], "target_level": 2},
            {"id": "dl_spreadsheets", "label": "Spreadsheet Skills", "description": "Structured data, formulas, validation, and summaries.", "prerequisites": ["dl_digital_foundations"], "target_level": 3},
            {"id": "dl_data_literacy", "label": "Data Literacy", "description": "Reading, questioning, and communicating with data.", "prerequisites": ["dl_spreadsheets"], "target_level": 3},
            {"id": "dl_ai_literacy", "label": "AI Literacy", "description": "Capabilities, limitations, prompting, and verification.", "prerequisites": ["dl_data_literacy", "dl_cyber_hygiene"], "target_level": 4},
            {"id": "dl_responsible_ai", "label": "Responsible AI", "description": "Bias, privacy, transparency, human oversight, and safe adoption.", "prerequisites": ["dl_ai_literacy"], "target_level": 4},
            # PS-02 "Digital Governance" named scope. Cybersecurity is covered by
            # dl_cyber_hygiene above; see ps02_coverage.py.
            {"id": "dl_data_privacy", "label": "Data Privacy", "description": "Personal data handling, minimization, consent, and retention duties.", "prerequisites": ["dl_cyber_hygiene"], "target_level": 4},
            {"id": "dl_digital_signatures", "label": "Digital Signatures", "description": "e-signing, certificates, non-repudiation, and document authenticity.", "prerequisites": ["dl_cyber_hygiene"], "target_level": 3},
            {"id": "dl_government_cloud", "label": "Government Cloud", "description": "Government cloud services, hosting policy, and shared infrastructure.", "prerequisites": ["dl_digital_foundations"], "target_level": 3},
            {"id": "dl_digital_public_infrastructure", "label": "Digital Public Infrastructure", "description": "Identity, payments, and data-exchange rails used across public services.", "prerequisites": ["dl_government_cloud", "dl_data_privacy"], "target_level": 3},
        ],
    },
}


def stamp_competency_provenance(catalog: dict = CURRICULA) -> None:
    """Give every competency its own source, authoring status and version.

    Stamped once at import rather than repeated on 34 literal entries: the
    values are uniform today (nothing is reviewed), but they live on the
    competency itself so a reviewer can later validate one competency without
    a data-model change -- the same per-item shape services/behavioral_anchors.py
    and services/role_targets.py use.
    """
    for curriculum in catalog.values():
        for competency in curriculum.get("competencies", []):
            competency.setdefault("source", curriculum.get("source", "internal-prototype"))
            competency.setdefault("authoring_status", PROVISIONAL)
            competency.setdefault("version", COMPETENCY_VERSION)


def validate_curricula(catalog: dict = CURRICULA) -> None:
    """Fail fast on duplicate IDs, dangling prerequisites, invalid levels, cycles,
    or a competency missing its provenance fields."""
    global_ids = set()
    for slug, curriculum in catalog.items():
        competencies = curriculum.get("competencies", [])
        local_ids = {item.get("id") for item in competencies}
        if not competencies or None in local_ids or len(local_ids) != len(competencies):
            raise ValueError(f"Curriculum {slug} must contain competencies with unique IDs")

        duplicates = global_ids.intersection(local_ids)
        if duplicates:
            raise ValueError(f"Competency IDs must be globally unique: {', '.join(sorted(duplicates))}")
        global_ids.update(local_ids)

        graph = {}
        for item in competencies:
            target = item.get("target_level")
            if not isinstance(target, int) or not 1 <= target <= 5:
                raise ValueError(f"{item['id']} must have a target_level from 1 to 5")
            missing_provenance = {"source", "authoring_status", "version"} - set(item)
            if missing_provenance:
                raise ValueError(
                    f"{item['id']} is missing provenance fields: {', '.join(sorted(missing_provenance))}"
                )
            prerequisites = list(item.get("prerequisites", []))
            unknown = set(prerequisites) - local_ids
            if unknown:
                raise ValueError(
                    f"{item['id']} has unknown prerequisites: {', '.join(sorted(unknown))}"
                )
            graph[item["id"]] = prerequisites

        visiting = set()
        visited = set()

        def visit(competency_id: str) -> None:
            if competency_id in visiting:
                raise ValueError(f"Curriculum {slug} contains a prerequisite cycle")
            if competency_id in visited:
                return
            visiting.add(competency_id)
            for prerequisite in graph[competency_id]:
                visit(prerequisite)
            visiting.remove(competency_id)
            visited.add(competency_id)

        for competency_id in graph:
            visit(competency_id)


def get_curriculum(slug: str) -> dict | None:
    curriculum = CURRICULA.get(slug)
    return deepcopy(curriculum) if curriculum else None


def curriculum_graph(slug: str) -> dict[str, list[str]]:
    curriculum = CURRICULA.get(slug, {})
    return {
        competency["id"]: list(competency.get("prerequisites", []))
        for competency in curriculum.get("competencies", [])
    }


def curriculum_for_topic(topic: str) -> tuple[str, dict] | tuple[None, None]:
    for slug, curriculum in CURRICULA.items():
        if any(item["id"] == topic for item in curriculum["competencies"]):
            return slug, deepcopy(curriculum)
    return None, None


def public_curricula() -> list[dict]:
    return [
        {
            "slug": slug,
            "name": curriculum["name"],
            "domain": curriculum["domain"],
            "description": curriculum["description"],
            "audience": curriculum["audience"],
            "level_band": curriculum["level_band"],
            "source": curriculum["source"],
            "competency_count": len(curriculum["competencies"]),
            "competencies": deepcopy(curriculum["competencies"]),
        }
        for slug, curriculum in CURRICULA.items()
    ]


stamp_competency_provenance()
validate_curricula()
