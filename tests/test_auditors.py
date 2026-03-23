"""Tests for app-auditor — no live HTTP required (uses mocking)."""
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


# ---------------------------------------------------------------------------
# website_auditor tests
# ---------------------------------------------------------------------------

def test_detect_nextjs_from_html():
    from app_auditor.website_auditor import detect_stack_from_html
    html = '<html><head></head><body><div id="__next"></div></body></html>'
    result = detect_stack_from_html(html)
    assert result["nextjs"] is True


def test_detect_vite_from_html():
    from app_auditor.website_auditor import detect_stack_from_html
    html = '<html><head><link rel="modulepreload" href="/assets/index-abc.js"></head></html>'
    result = detect_stack_from_html(html)
    assert result["vite"] is True


def test_detect_supabase_from_html():
    from app_auditor.website_auditor import detect_stack_from_html
    html = '<script src="https://cdn.supabase.co/supabase.js"></script>'
    result = detect_stack_from_html(html)
    assert result["supabase"] is True


def test_empty_html_returns_all_false():
    from app_auditor.website_auditor import detect_stack_from_html
    result = detect_stack_from_html("")
    assert all(v is False for v in result.values())


def test_infer_risks_vite():
    from app_auditor.website_auditor import infer_risks
    risks = infer_risks({"vite": True, "supabase": False, "react": False, "nextjs": False, "vercel": False, "netlify": False, "vue": False})
    assert any("vite" in r.lower() or "spa" in r.lower() for r in risks)


def test_infer_risks_supabase():
    from app_auditor.website_auditor import infer_risks
    risks = infer_risks({"vite": False, "supabase": True, "react": False, "nextjs": False, "vercel": False, "netlify": False, "vue": False})
    assert any("supabase" in r.lower() or "rls" in r.lower() for r in risks)


def test_audit_url_unreachable_returns_ok_false():
    from app_auditor.website_auditor import audit_url
    result = audit_url("https://this-url-does-not-exist-xyz-12345.invalid")
    assert result["ok"] is False
    assert "error" in result


# ---------------------------------------------------------------------------
# github_auditor tests
# ---------------------------------------------------------------------------

def test_parse_repo_url_full():
    from app_auditor.github_auditor import parse_repo_url
    assert parse_repo_url("https://github.com/vercel/next.js") == ("vercel", "next.js")


def test_parse_repo_url_shorthand():
    from app_auditor.github_auditor import parse_repo_url
    assert parse_repo_url("facebook/react") == ("facebook", "react")


def test_parse_repo_url_invalid():
    from app_auditor.github_auditor import parse_repo_url
    assert parse_repo_url("not-a-url") is None
    assert parse_repo_url("") is None


def test_analyze_repo_url_invalid_returns_error():
    from app_auditor.github_auditor import analyze_repo_url
    result = analyze_repo_url("not-a-github-url")
    assert result["ok"] is False
    assert "error" in result


def test_analyze_repo_detects_docker(monkeypatch):
    """Mock GitHub API to return a tree with Dockerfile."""
    from app_auditor import github_auditor

    def mock_get_repo_tree(owner, repo):
        return [
            {"path": "Dockerfile"},
            {"path": "package.json"},
            {"path": ".github/workflows/ci.yml"},
            {"path": ".env.example"},
        ]

    def mock_get_repo_info(owner, repo):
        return {"full_name": f"{owner}/{repo}", "default_branch": "main"}

    monkeypatch.setattr(github_auditor, "get_repo_tree", mock_get_repo_tree)
    monkeypatch.setattr(github_auditor, "get_repo_info", mock_get_repo_info)
    monkeypatch.setattr(github_auditor, "_fetch_file_content", lambda *a: None)

    result = github_auditor.analyze_repo("myorg", "myrepo")
    assert result["ok"] is True
    assert result["detected"]["docker"] is True
    assert result["detected"]["github_actions"] is True
    assert result["detected"]["env_example"] is True
    # No Dockerfile missing warning since it's present
    assert not any("dockerfile" in m.lower() for m in result["missing"])
