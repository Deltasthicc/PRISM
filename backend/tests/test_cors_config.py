"""CORS origin configuration -- see main.py's FRONTEND_ORIGINS/FRONTEND_ORIGIN_REGEX.

Real regression coverage for the Vercel CORS gap: the hosted frontend moved
from "no hosted frontend exists" to a real Vercel deployment, and Vercel
gives every deployment (the stable production alias, plus a fresh one for
every preview build) its own unique *.vercel.app subdomain. Without a
pattern match, every new preview URL would need a manual FRONTEND_ORIGINS
edit and redeploy before that preview could ever reach the API.
"""
import re

from main import FRONTEND_ORIGIN_REGEX, frontend_origins


def test_default_frontend_origins_still_include_local_dev_ports():
    assert "http://localhost:3000" in frontend_origins
    assert "http://127.0.0.1:3000" in frontend_origins


def test_regex_matches_the_real_production_vercel_domain():
    assert re.match(FRONTEND_ORIGIN_REGEX, "https://prism-iota-azure.vercel.app")


def test_regex_matches_a_realistic_preview_deployment_domain():
    # Vercel's actual preview-URL shape: <project>-<hash>-<team>-projects.vercel.app
    assert re.match(
        FRONTEND_ORIGIN_REGEX,
        "https://prism-3z4ine58c-shashwatrajan2005-3834s-projects.vercel.app",
    )


def test_regex_rejects_a_different_vercel_project():
    # Must not trust every Vercel-hosted site -- only this project's own subdomains.
    assert not re.match(FRONTEND_ORIGIN_REGEX, "https://some-other-app.vercel.app")


def test_regex_rejects_non_https_and_lookalike_hosts():
    assert not re.match(FRONTEND_ORIGIN_REGEX, "http://prism-iota-azure.vercel.app")
    assert not re.match(
        FRONTEND_ORIGIN_REGEX, "https://prism-iota-azure.vercel.app.evil.com"
    )
    assert not re.match(FRONTEND_ORIGIN_REGEX, "https://prismXiota-azure.vercel.app")
