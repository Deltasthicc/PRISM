"""Data-driven curricula used by the game and the skill-intelligence layer.

Competency identifiers are globally unique because the current
``accuracy_history`` table is keyed by ``(player_id, topic)``. Keeping the
catalog in one module removes the old DSA-only knowledge-graph assumption
without pretending that this in-repository seed data is the authoritative
iGOT or Karmayogi Competency Model catalog.
"""

import json
import os
from copy import deepcopy

# Hand-translated (see scripts/generate_curricula_hi.py's docstring for why
# not machine-generated this time) Hindi overlay for the fields actually
# rendered to a learner: curriculum name/domain/description/audience/
# level_band and each competency's label/description. Deliberately does NOT
# cover COMPETENCY_SOURCES' citation excerpts or SOURCES' title/publisher --
# those are literal references to real government documents, and
# paraphrase-translating a citation misrepresents it rather than localizing
# it; neither is shown to a learner today regardless.
_TRANSLATIONS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "curricula_hi.json")
with open(_TRANSLATIONS_PATH, encoding="utf-8") as _handle:
    _CURRICULA_HI: dict = json.load(_handle)


# docs/internal/SIH26101_TEAM_ORCHESTRATION.md section 5, Lane 3 acceptance evidence:
# "Every competency/target has source, authoring status and version." The
# per-curriculum `source` key below records origin; `authoring_status` records
# assurance using the fixed documented vocabulary (CODEX.md architectural
# invariants), and PROVISIONAL is the only honest value until a named domain
# reviewer validates this taxonomy -- SIH26101_MASTER_CHECKLIST.md section 4.1
# marks that BLOCKED-EXTERNAL.
PROVISIONAL = "PROVISIONAL"
COMPETENCY_VERSION = 1

# Bumped from 1 when a competency's *citation* changes, independently of
# COMPETENCY_VERSION (which versions the competency definition itself). A
# consumer that has cached a source record needs to know the citation moved
# even when the label/description/target did not.
SOURCE_REGISTRY_VERSION = 1

# The date every URL below was fetched and confirmed to resolve. Recorded
# because a government publication can move or be withdrawn: a reader must be
# able to tell "cited from a live page on this date" from "still live today".
RETRIEVED_ON = "2026-09-06"

# Government-published sources backing the taxonomy. IDs are stable and are
# meant to be cited in seed comments and PR descriptions the same way the team
# cites PS-01..PS-18.
#
# `status` uses the fixed documented vocabulary (CODEX.md architectural
# invariants). OFFICIAL means "published by a government body and usable as a
# primary citation"; CATALOGUE means "a real published record that is NOT a
# live provider sync". Neither is an endorsement of this taxonomy -- see
# `authoring_status`, which stays PROVISIONAL regardless of how strong the
# source is. A source proves the competency is a real thing the Government of
# India trains people on; only a named domain reviewer can validate that our
# level targets and anchors for it are right.
SOURCES: dict[str, dict] = {
    "SRC-01": {
        "title": "NSSTA Training Calendar 2021-22",
        "publisher": "MoSPI / NSO / National Statistical Systems Training Academy",
        "url": (
            "https://mospi.gov.in/sites/default/files/main_menu/training/"
            "Training%20Calendar%20of%20NSSTA%20for%20FY%202021-22.pdf"
        ),
        "published": "2021",
        "status": "OFFICIAL",
    },
    "SRC-02": {
        "title": "iGOT Karmayogi course recommendations, National Learning Week 2024",
        "publisher": "Karmayogi Bharat / iGOT Karmayogi",
        "url": (
            "https://portal.igotkarmayogi.gov.in/content-store/orgStore/0133809553768366080/"
            "1729231972061_Course%20Recommendations_Karmayogi%20Saptah.pdf"
        ),
        "published": "2024",
        "status": "CATALOGUE",
    },
    "SRC-03": {
        "title": "Karmayogi Competency Model (KCM)",
        "publisher": "Capacity Building Commission",
        "url": "https://cbc.gov.in/karmyogi-competency-model-kcm",
        "published": "2024-10-19",
        "status": "OFFICIAL",
    },
    "SRC-04": {
        "title": "Karmayogi Quality Framework, v1",
        "publisher": "Capacity Building Commission",
        "url": "https://cbc.gov.in/sites/default/files/2026-05/Final_KQF_v1_merged%20%281%29_0.pdf",
        "published": "2026",
        "status": "OFFICIAL",
    },
    "SRC-05": {
        "title": "SDG National Indicator Framework 2026, with metadata",
        "publisher": "MoSPI",
        "url": (
            "https://www.mospi.gov.in/uploads/publications_reports/"
            "publications_reports1782719243840_1f31af3d-72ef-43f0-8038-c029553699f3_"
            "SDG_NIF_2026_(along_with_metadata).pdf"
        ),
        "published": "2026",
        "status": "OFFICIAL",
    },
    "SRC-06": {
        "title": "Metadata of the National Indicator Framework",
        "publisher": "MoSPI",
        "url": "https://www.mospi.gov.in/metadata-national-indicator-framework",
        "published": "",
        "status": "OFFICIAL",
    },
    "SRC-07": {
        "title": "SIF Guideline, version 1.1",
        "publisher": "MoSPI",
        "url": "https://www.mospi.gov.in/sites/default/files/SIF%20Guideline%20by%20MoSPI.pdf",
        "published": "2019-07",
        "status": "OFFICIAL",
    },
    "SRC-08": {
        "title": "COCSSO presentation, Coordination and Publication Division (NQAF assessment)",
        "publisher": "MoSPI",
        "url": (
            "https://mospi.gov.in/sites/default/files/cocsso/Presentation/"
            "Coordination%20and%20publication%20division.pdf"
        ),
        "published": "",
        "status": "OFFICIAL",
    },
    "SRC-09": {
        "title": "Open Government Data Platform India -- SDG NIF catalogue and resource API",
        "publisher": "data.gov.in / NIC",
        "url": (
            "https://www.data.gov.in/catalog/"
            "sustainable-development-goals-national-indicator-framework"
        ),
        "published": "",
        "status": "OFFICIAL",
    },
    "SRC-11": {
        "title": "NIELIT course catalogue",
        "publisher": "NIELIT, Ministry of Electronics & Information Technology",
        "url": "https://www.nielit.gov.in/content/online-course-cyber-security-tools",
        "published": "",
        "status": "CATALOGUE",
    },
    "SRC-12": {
        "title": "C-DAC education and training programmes",
        "publisher": "C-DAC, Ministry of Electronics & Information Technology",
        "url": "https://www.cdac.in/index.aspx?id=education",
        "published": "",
        "status": "CATALOGUE",
    },
    "SRC-13": {
        "title": "Skill India Digital Hub master catalogue",
        "publisher": "Ministry of Skill Development & Entrepreneurship / NCVET",
        "url": "https://www.skillindiadigital.gov.in/about-us",
        "published": "",
        "status": "CATALOGUE",
    },
}

# Marks how directly a source backs its competency, so a reviewer can triage.
# DIRECT: the source names a programme/module on this subject outright.
# INDIRECT: the subject appears only inside a broader course's content list, or
# is reached through an adjacent programme. An INDIRECT citation is an honest
# "this is the best government source we found", not a claim of coverage --
# docs/internal/SIH26101_WINNING_PLAYBOOK.md section 2 forbids dressing a weak source up.
DIRECT = "DIRECT"
INDIRECT = "INDIRECT"

# No government source is claimed for the DSA curriculum: it is an engineering
# sample, not the pitch centre (SIH26101_MASTER_CHECKLIST.md section 3.3), and
# inventing a MoSPI citation for "Binary Search Trees" would be exactly the
# fabricated provenance the truth boundary forbids. Those competencies keep
# source="internal-prototype" and are absent from this map by design.
#
# competency_id -> (source_id, what in that source backs it, strength)
COMPETENCY_SOURCES: dict[str, tuple[str, str, str]] = {
    # -- Official Statistics ------------------------------------------------
    "os_statistical_foundations": (
        "SRC-01",
        "SSS induction module 'Basic Statistical Techniques': presentation of statistical data, "
        "probability, frequency distribution, central tendency/dispersion, correlation and "
        "regression, time series, index numbers",
        DIRECT,
    ),
    "os_data_collection": (
        "SRC-01",
        "ISS probationer module 10, 'Survey methodology (4 weeks) and Data Analytics (4 weeks)', "
        "covering designing, building, collecting and processing survey data",
        DIRECT,
    ),
    "os_sampling_design": (
        "SRC-01",
        "SSS induction module 'Sample Survey Techniques': simple random, systematic, stratified, "
        "cluster and PPS sampling; sampling and non-sampling error; standard error; efficiency",
        DIRECT,
    ),
    "os_data_quality": (
        "SRC-08",
        "Assessment of the Indian Statistical System against the National Quality Assurance "
        "Framework -- metadata management, legislative framework and quality measures by "
        "production stage",
        DIRECT,
    ),
    "os_official_statistics": (
        "SRC-01",
        "SSS induction module 'Official Statistics' (two weeks): functions of MoSPI, statistical "
        "set-up in line ministries, sources of official statistics, the Collection of Statistics "
        "Act 2008",
        DIRECT,
    ),
    "os_visualization": (
        "SRC-02",
        "'Data Storytelling' (Fractal, 2 hr 49 min), recommended for JS & Above",
        DIRECT,
    ),
    "os_gis": (
        "SRC-01",
        "ISS probationer module 17, 'Application of GIS, Environment Statistics and Activities of "
        "Labour Bureau' (IIRS & FSI, Dehradun; two weeks)",
        DIRECT,
    ),
    "os_big_data": (
        "SRC-01",
        "ISS probationer module 15, 'Core IT including a part of Big Data, Data Warehousing and "
        "Data Analytics' (12 weeks); domain course 'Big Data Analysis'",
        DIRECT,
    ),
    "os_ml": (
        "SRC-01",
        "Domain course 14, 'Training on Artificial Intelligence and Machine learning' "
        "(IIT Madras, two weeks); course 8 covers AI/ML with a focus on official statistics",
        DIRECT,
    ),
    "os_survey_design": (
        "SRC-01",
        "Domain course 1, 'Planning and Designing of large scale sample surveys' (NSSTA, one "
        "week): survey planning, frame, sampling scheme, sample size, questionnaire design, "
        "post-survey operations",
        DIRECT,
    ),
    "os_national_accounts": (
        "SRC-01",
        "Domain course 12, 'National Accounts' (NSSTA / IMF SARTTAC); an ISS probationer module; "
        "a named Specialized Training Programme core area",
        DIRECT,
    ),
    "os_price_statistics": (
        "SRC-01",
        "SSS induction 'Economic Statistics: Price Statistics -- CPI & WPI'; an ISS probationer "
        "module; a named Specialized Training Programme core area",
        DIRECT,
    ),
    "os_labour_statistics": (
        "SRC-01",
        "Domain course 7, 'Labour Force and Employment' (NSSTA, one week): labour market "
        "segmentation, underemployment, informal and unpaid work, compiling labour statistics",
        DIRECT,
    ),
    "os_agricultural_statistics": (
        "SRC-01",
        "SSS induction module on Agricultural & Allied Statistics and the System of Agricultural "
        "Statistics in India, including Animal Husbandry, Dairying and Fisheries",
        DIRECT,
    ),
    "os_industrial_statistics": (
        "SRC-01",
        "SSS induction module on Industrial Statistics: Annual Survey of Industries, Index of "
        "Industrial Production, Economic Census and follow-up surveys",
        DIRECT,
    ),
    "os_sdg_indicators": (
        "SRC-05",
        "National Indicator Framework indicator definitions, data sources, periodicity and "
        "per-indicator metadata",
        DIRECT,
    ),
    "os_metadata_standards": (
        "SRC-06",
        "MoSPI guiding principles for metadata development and standardisation across all NIF "
        "indicators",
        DIRECT,
    ),
    "os_statistical_programming": (
        "SRC-01",
        "Domain course 10, 'Python Training for Statisticians' (C R Rao AIMSC) with a "
        "module-level syllabus, and course 2, 'Handling Large Scale Data & Data Analysis using R' "
        "(IIT Kanpur / IASRI) on live NSSO and Census unit-level data. SAS and SPSS appear in "
        "course 5's content list; Stata is named by no source in the register",
        DIRECT,
    ),
    "os_data_management_sql": (
        "SRC-01",
        "Domain course 11, 'Data Analysts and Data Ware House' (C R Rao AIMSC): ETL, schema and "
        "dimension modelling, ER modelling and SQL script generation",
        DIRECT,
    ),
    "os_apis_interoperability": (
        "SRC-09",
        "Documented resource API over published government datasets on the OGD platform",
        INDIRECT,
    ),
    "os_open_data": (
        "SRC-09",
        "The OGD platform itself: open formats, catalogue structure and published release policy",
        DIRECT,
    ),
    # -- Public Policy & Programme Evaluation -------------------------------
    "pa_governance_foundations": (
        "SRC-03",
        "The KCM's role-based governance framing and its Chaar Gunas, including Rajyakarma "
        "(understanding governance systems) and Svadharma (serving citizens)",
        INDIRECT,
    ),
    "pa_policy_design": (
        "SRC-02",
        "'Public Policy Writing' (Indian School of Public Policy, 2 hr 45 min) and 'Public Policy "
        "and the VUCA World' (IIPA, 2 hr 7 min)",
        DIRECT,
    ),
    "pa_public_finance": (
        "SRC-02",
        "'Finance for Non-finance professionals' (NSE Academy, 55 min); SRC-01's ISS probationer "
        "module 22 covers budgeting and financial management (NIFM, Faridabad)",
        DIRECT,
    ),
    "pa_program_management": (
        "SRC-02",
        "'Fundamentals of Program and Project Management' (Quality Council of India, 9 hr 5 min); "
        "Project Management is a named KCM functional competency",
        DIRECT,
    ),
    "pa_monitoring_evaluation": (
        "SRC-01",
        "ISS probationer module 13, 'Monitoring & Evaluation' (ASCI, Hyderabad)",
        DIRECT,
    ),
    "pa_impact_evaluation": (
        "SRC-01",
        "ISS probationer module 5, 'Time Series and Applied Econometrics' (ISEC Bangalore), and "
        "module 4, 'Poverty & Inequality Estimation'",
        INDIRECT,
    ),
    "pa_data_storytelling": (
        "SRC-02",
        "'Data Storytelling' (Fractal, 2 hr 49 min)",
        DIRECT,
    ),
    "pa_leadership": (
        "SRC-01",
        "MCTP Phase 3, 'One week training on Leadership and Strategic Management'. The KCM "
        "(SRC-03) additionally defines five leadership competencies",
        DIRECT,
    ),
    "pa_communication": (
        "SRC-01",
        "Domain course 9, 'Communication Skill Development' (IIM Ahmedabad) with a full content "
        "breakdown, and ISS probationer module 19, 'Communication & Presentation Skill' "
        "(IIPA / NSSTA, two weeks)",
        DIRECT,
    ),
    "pa_ethics": (
        "SRC-04",
        "The Karmayogi Quality Framework's seventh commitment, ethical and values alignment: "
        "learning on iGOT must be civic formation, not compliance training. No dedicated ethics "
        "course appears in the register",
        INDIRECT,
    ),
    "pa_decision_making": (
        "SRC-02",
        "'Human Decision Making and its Biases' (Fractal, 2 hr 18 min), 'Structured Approach to "
        "Problem Solving' (Fractal) and 'Critical Thinking' (ISB Hyderabad)",
        DIRECT,
    ),
    "pa_change_management": (
        "SRC-03",
        "'Vigilance & Change Management' is a named KCM functional competency",
        DIRECT,
    ),
    # -- Digital & AI Literacy ----------------------------------------------
    "dl_digital_foundations": (
        "SRC-11",
        "NIELIT Digital Literacy Courses (DLC)",
        DIRECT,
    ),
    "dl_cyber_hygiene": (
        "SRC-11",
        "NIELIT 'Online Course on Cyber Security Tools' and 'Certificate Course on Cyber Security "
        "(Online)'; SRC-02 lists 'Cyber Security' (UpGrad, 2 hr 56 min)",
        DIRECT,
    ),
    "dl_collaboration": (
        "SRC-13",
        "Skill India Digital Hub master catalogue entries carrying an NSQF level and stated "
        "learning outcomes",
        INDIRECT,
    ),
    "dl_spreadsheets": (
        "SRC-11",
        "NIELIT non-formal course tracks (O/A/B/C levels) covering office productivity tooling",
        INDIRECT,
    ),
    "dl_data_literacy": (
        "SRC-02",
        "'Data Storytelling' (Fractal, 2 hr 49 min), recommended across grades",
        DIRECT,
    ),
    "dl_ai_literacy": (
        "SRC-02",
        "'Gen AI for Everyone' (Fractal, 2 hr 49 min) and 'Introduction to Emerging Technologies' "
        "(Wadhwani Foundation, 2 hr 20 min)",
        DIRECT,
    ),
    "dl_responsible_ai": (
        "SRC-02",
        "'ChatGPT and Generative AI tools for Government Officials' (Wadhwani Foundation, 1 hr)",
        INDIRECT,
    ),
    "dl_data_privacy": (
        "SRC-02",
        "'Digital Personal Data Protection Act, 2023: An Overview' (Karmayogi Bharat, 1 hr 12 "
        "min) -- an official course on the governing Indian statute",
        DIRECT,
    ),
    "dl_digital_signatures": (
        "SRC-12",
        "C-DAC cyber security and PKI-adjacent programmes. No course in the register is "
        "specifically on digital signatures; the Controller of Certifying Authorities is the "
        "unexplored next source",
        INDIRECT,
    ),
    "dl_government_cloud": (
        "SRC-11",
        "NIELIT 'Certificate Course on Cyber Security & Cloud Computing'. No source in the "
        "register covers government cloud policy itself; MeghRaj / GI-Cloud is the unexplored "
        "next source",
        INDIRECT,
    ),
    "dl_digital_public_infrastructure": (
        "SRC-13",
        "Skill India Digital Hub describes itself as digital public infrastructure for skilling, "
        "built on Aadhaar-based identity, NCVET-aligned credentialing and DigiLocker storage",
        DIRECT,
    ),
}


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


def source_record(source_id: str) -> dict | None:
    """Return one citation from SOURCES with its stable ID and retrieval date.

    Copied, not shared: a consumer that mutates the returned dict must not be
    able to rewrite the registry every later caller reads.
    """
    entry = SOURCES.get(source_id)
    if not entry:
        return None
    return {"source_id": source_id, "retrieved": RETRIEVED_ON, **deepcopy(entry)}


def source_registry() -> dict:
    """The full citation registry, for Lane 5's evidence view and Lane 6's
    evidence matrix. Exposed as a function rather than the bare SOURCES dict so
    callers get a copy and the registry version travels with it."""
    return {
        "registry_version": SOURCE_REGISTRY_VERSION,
        "retrieved": RETRIEVED_ON,
        "sources": {source_id: source_record(source_id) for source_id in SOURCES},
    }


def stamp_competency_provenance(catalog: dict = CURRICULA) -> None:
    """Give every competency its own source, authoring status and version.

    Stamped once at import rather than repeated on 45 literal entries, so a
    citation is edited in exactly one place (COMPETENCY_SOURCES) and cannot
    drift from the competency it describes.

    `source` stays a plain string for backwards compatibility -- Lane 1's
    AcademyHub.jsx calls `.includes()` on the curriculum-level value, and
    test_competency_status_vocabulary.py asserts the competency-level one is
    truthy. What changes is *which* string: a mapped competency now carries its
    stable source ID ("SRC-01") instead of the flat "demo" inherited from its
    curriculum, and the full citation rides alongside in `source_record`.

    `authoring_status` deliberately stays PROVISIONAL even for a competency
    with a DIRECT government citation. The source proves the subject is real
    and trained-on; it says nothing about whether our target level, prerequisite
    edges and behavioural anchors for it are right. Only a named domain reviewer
    changes that, and SIH26101_MASTER_CHECKLIST.md section 4.1 marks that
    BLOCKED-EXTERNAL.
    """
    for curriculum in catalog.values():
        for competency in curriculum.get("competencies", []):
            citation = COMPETENCY_SOURCES.get(competency["id"])
            if citation:
                source_id, detail, strength = citation
                competency.setdefault("source", source_id)
                competency.setdefault("source_record", source_record(source_id))
                competency.setdefault("source_detail", detail)
                competency.setdefault("source_strength", strength)
            else:
                # No government citation claimed. Recorded as an explicit
                # absence rather than an empty string, so a consumer can tell
                # "we looked and found none" from "nobody filled this in".
                competency.setdefault("source", "internal-prototype")
                competency.setdefault("source_record", None)
                competency.setdefault("source_detail", "")
                competency.setdefault("source_strength", "")
            competency.setdefault("authoring_status", PROVISIONAL)
            competency.setdefault("version", COMPETENCY_VERSION)
            competency.setdefault("source_registry_version", SOURCE_REGISTRY_VERSION)


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
            # A citation that points at a source we do not carry is worse than
            # no citation: it reads as evidence while proving nothing. Fail at
            # import, the same way ps02_coverage.py refuses to load on a
            # dangling PS-02 mapping.
            if item["source"] != "internal-prototype" and item["source"] not in SOURCES:
                raise ValueError(
                    f"{item['id']} cites unknown source {item['source']!r}; add it to SOURCES"
                )
            if item["source_strength"] not in (DIRECT, INDIRECT, ""):
                raise ValueError(
                    f"{item['id']} has invalid source_strength {item['source_strength']!r}"
                )
            if item["source"] != "internal-prototype" and not item["source_detail"]:
                raise ValueError(
                    f"{item['id']} cites {item['source']} without saying what in it applies"
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

    # The reverse direction: a citation written for a competency that was
    # later renamed or removed would otherwise sit in COMPETENCY_SOURCES
    # silently doing nothing, and the next reader would trust a map that no
    # longer applies.
    orphaned = sorted(set(COMPETENCY_SOURCES) - global_ids)
    if orphaned:
        raise ValueError(
            f"COMPETENCY_SOURCES cites competencies that do not exist: {', '.join(orphaned)}"
        )


def _localize(curriculum: dict, slug: str, lang: str) -> dict:
    """Overlay the Hindi translation onto a copy of `curriculum`, field by
    field -- never mutates the English source, and any field missing from
    the translation (should not happen; see scripts/generate_curricula_hi.py's
    validate_shape) silently falls back to English rather than raising."""
    if lang != "hi":
        return curriculum
    translation = _CURRICULA_HI.get(slug)
    if not translation:
        return curriculum
    for field in ("name", "domain", "description", "audience", "level_band"):
        if translation.get(field):
            curriculum[field] = translation[field]
    translated_competencies = translation.get("competencies", {})
    for competency in curriculum.get("competencies", []):
        translated = translated_competencies.get(competency["id"])
        if not translated:
            continue
        if translated.get("label"):
            competency["label"] = translated["label"]
        if translated.get("description"):
            competency["description"] = translated["description"]
    return curriculum


def get_curriculum(slug: str, lang: str = "en") -> dict | None:
    curriculum = CURRICULA.get(slug)
    if not curriculum:
        return None
    return _localize(deepcopy(curriculum), slug, lang)


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


def public_curricula(lang: str = "en") -> list[dict]:
    return [
        {
            "slug": slug,
            "name": localized["name"],
            "domain": localized["domain"],
            "description": localized["description"],
            "audience": localized["audience"],
            "level_band": localized["level_band"],
            "source": curriculum["source"],
            "competency_count": len(localized["competencies"]),
            "competencies": localized["competencies"],
        }
        for slug, curriculum in CURRICULA.items()
        for localized in [_localize(deepcopy(curriculum), slug, lang)]
    ]


stamp_competency_provenance()
validate_curricula()
