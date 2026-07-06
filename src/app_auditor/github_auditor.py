"""
GitHub repo auditor: analyze a public repo's structure and report stack, missing files, and suggestions.
"""
import base64
import logging
import os
import re
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

# Timeouts and retries
GITHUB_TIMEOUT = 25
GITHUB_HEADERS: Optional[Dict[str, str]] = None


def _github_headers() -> Dict[str, str]:
    global GITHUB_HEADERS
    if GITHUB_HEADERS is not None:
        return GITHUB_HEADERS
    token = os.getenv("GITHUB_TOKEN")
    h = {"Accept": "application/vnd.github+json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    GITHUB_HEADERS = h
    return h


def parse_repo_url(url: str) -> Optional[tuple[str, str]]:
    """Return (owner, repo) or None if invalid."""
    url = url.strip().rstrip("/")
    # https://github.com/owner/repo or github.com/owner/repo
    m = re.match(r"(?:https?://)?(?:www\.)?github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$", url, re.I)
    if m:
        return m.group(1), m.group(2)
    # owner/repo
    if "/" in url and " " not in url and len(url) < 100:
        parts = url.split("/", 1)
        if len(parts) == 2 and parts[0] and parts[1]:
            return parts[0], parts[1]
    return None


def get_repo_tree(owner: str, repo: str) -> List[Dict[str, Any]]:
    """Fetch repo file tree (recursive). Raises on HTTP error."""
    url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/HEAD?recursive=1"
    r = requests.get(url, headers=_github_headers(), timeout=GITHUB_TIMEOUT)
    r.raise_for_status()
    data = r.json()
    return data.get("tree") or []


def get_repo_info(owner: str, repo: str) -> Dict[str, Any]:
    """Fetch repo metadata (description, default branch, etc.)."""
    url = f"https://api.github.com/repos/{owner}/{repo}"
    r = requests.get(url, headers=_github_headers(), timeout=GITHUB_TIMEOUT)
    if r.status_code != 200:
        return {}
    return r.json()


def get_readme(owner: str, repo: str) -> Optional[str]:
    """Fetch README content if present."""
    url = f"https://api.github.com/repos/{owner}/{repo}/readme"
    r = requests.get(url, headers={**_github_headers(), "Accept": "application/vnd.github.raw"}, timeout=GITHUB_TIMEOUT)
    if r.status_code != 200:
        return None
    return r.text[:8000]


# Production-readiness checklist. Each entry: (key, label, severity, why,
# predicate over the set of repo paths). Severity drives the score weight and
# whether it lands in "missing" (warn/critical) vs "info".
CHECKLIST = [
    ("dockerfile", "Dockerfile", "warn",
     "Containerize for reproducible production deploys.",
     lambda paths: any(p in paths for p in ("Dockerfile", "Dockerfile.dev", "docker/Dockerfile"))),
    ("github_actions", "GitHub Actions CI", "warn",
     "Add CI/CD to test and ship every push.",
     lambda paths: any(p.startswith(".github/workflows/") for p in paths)),
    ("env_example", ".env.example", "warn",
     "Document required env vars so deploys don't fail silently.",
     lambda paths: any(p in paths for p in (".env.example", "env.example", ".env.sample", ".env.template"))),
    ("readme", "README", "critical",
     "Explain what the project is and how to run it.",
     lambda paths: any(p.lower().startswith("readme") for p in paths)),
    ("license", "LICENSE", "warn",
     "State usage rights for a public repo.",
     lambda paths: any(p.lower().split("/")[-1].startswith(("license", "licence", "copying")) for p in paths)),
    ("gitignore", ".gitignore", "info",
     "Avoid committing secrets, build output and deps.",
     lambda paths: ".gitignore" in paths),
    ("tests", "Test suite", "warn",
     "Add automated tests to catch regressions.",
     lambda paths: any(
         re.search(r"(^|/)(tests?|__tests__|spec)/", "/" + p)
         or re.search(r"\.(test|spec)\.[jt]sx?$", p)
         or p.endswith("_test.py") or p.startswith("test_")
         for p in paths)),
    ("lockfile", "Dependency lockfile", "warn",
     "Pin dependency versions for reproducible builds.",
     lambda paths: any(p in paths for p in (
         "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "bun.lockb",
         "poetry.lock", "requirements.txt", "Pipfile.lock", "uv.lock", "Cargo.lock", "go.sum"))),
    ("editorconfig", ".editorconfig", "info",
     "Keep formatting consistent across editors.",
     lambda paths: ".editorconfig" in paths),
]

# Map a file extension to a language label, for the file-tree breakdown.
EXT_LANG = {
    "ts": "TypeScript", "tsx": "TypeScript", "js": "JavaScript", "jsx": "JavaScript",
    "mjs": "JavaScript", "cjs": "JavaScript", "py": "Python", "rb": "Ruby",
    "go": "Go", "rs": "Rust", "java": "Java", "kt": "Kotlin", "php": "PHP",
    "css": "CSS", "scss": "CSS", "html": "HTML", "vue": "Vue", "svelte": "Svelte",
    "json": "JSON", "yml": "YAML", "yaml": "YAML", "md": "Markdown", "sh": "Shell",
    "sql": "SQL", "toml": "TOML",
}


def language_breakdown(tree: List[Dict[str, Any]]) -> Dict[str, int]:
    """Count files per language from the repo tree (blobs only)."""
    counts: Dict[str, int] = {}
    for item in tree:
        if item.get("type") and item["type"] != "blob":
            continue
        path = item.get("path", "")
        ext = path.rsplit(".", 1)[-1].lower() if "." in path.split("/")[-1] else ""
        lang = EXT_LANG.get(ext)
        if lang:
            counts[lang] = counts.get(lang, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: -kv[1]))


def analyze_repo(owner: str, repo: str) -> Dict[str, Any]:
    """
    Analyze repo structure and return detected stack, missing items, and migration suggestions.
    """
    try:
        tree = get_repo_tree(owner, repo)
    except requests.RequestException as e:
        logger.warning("get_repo_tree failed: %s", e)
        return {
            "ok": False,
            "error": str(e),
            "detected": {},
            "missing": [],
            "suggestions": ["Could not fetch repo; check URL and token."],
        }

    blobs = [item for item in tree if item.get("type", "blob") == "blob"]
    paths = [item["path"] for item in tree]
    path_set = set(paths)
    detected = {
        "nextjs": any(
            p in paths for p in ("next.config.js", "next.config.mjs", "next.config.ts")
        ),
        "vite": any(
            p in paths for p in ("vite.config.ts", "vite.config.js", "vite.config.mts")
        ),
        "react": False,
        "docker": any(p in paths for p in ("Dockerfile", "Dockerfile.dev")),
        "github_actions": any(p.startswith(".github/workflows/") for p in paths),
        "supabase": any("supabase" in p.lower() for p in paths),
        "vercel": "vercel.json" in paths or any(p.startswith(".vercel") for p in paths),
        "env_example": ".env.example" in paths or "env.example" in paths,
    }

    if "package.json" in paths:
        try:
            content = _fetch_file_content(owner, repo, "package.json")
            if content and "react" in content.lower():
                detected["react"] = True
        except Exception:
            pass
    if not detected["react"] and "react" in " ".join(paths).lower():
        detected["react"] = True

    # Run the full production-readiness checklist.
    checklist = []
    for key, label, severity, why, predicate in CHECKLIST:
        present = bool(predicate(path_set))
        checklist.append({
            "key": key, "label": label, "severity": severity,
            "why": why, "present": present,
        })

    # `missing` keeps the legacy human-readable strings (for back-compat),
    # now derived from the checklist warn/critical items that are absent.
    missing = [
        f"No {c['label']} found - {c['why']}"
        for c in checklist
        if not c["present"] and c["severity"] in ("warn", "critical")
    ]

    # Score: 100 minus weighted penalties for absent items.
    weight = {"critical": 25, "warn": 10, "info": 3}
    penalty = sum(weight[c["severity"]] for c in checklist if not c["present"])
    score = max(0, 100 - penalty)
    grade = "A+" if score >= 95 else "A" if score >= 85 else "B" if score >= 70 \
        else "C" if score >= 55 else "D" if score >= 40 else "F"

    suggestions = []
    if detected["vite"] and not detected["docker"]:
        suggestions.append("Vite SPA: add Dockerfile and ensure server rewrite rules for SPA routing.")
    if detected["supabase"]:
        suggestions.append("Supabase: verify RLS, auth flow, and env key exposure in client.")
    if detected["nextjs"]:
        suggestions.append("Next.js: check output mode (standalone/docker) and env at build time.")

    return {
        "ok": True,
        "owner": owner,
        "repo": repo,
        "detected": detected,
        "checklist": checklist,
        "missing": missing,
        "score": score,
        "grade": grade,
        "file_count": len(blobs),
        "languages": language_breakdown(tree),
        "suggestions": suggestions or ["Review security and env handling before production."],
        "repo_info": get_repo_info(owner, repo),
    }


def _fetch_file_content(owner: str, repo: str, path: str) -> Optional[str]:
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    r = requests.get(url, headers=_github_headers(), timeout=GITHUB_TIMEOUT)
    if r.status_code != 200:
        return None
    data = r.json()
    if data.get("encoding") == "base64":
        return base64.b64decode(data.get("content", "")).decode("utf-8", errors="ignore")
    return None


def analyze_repo_url(repo_url: str) -> Dict[str, Any]:
    """Convenience: parse URL and run analyze_repo."""
    parsed = parse_repo_url(repo_url)
    if not parsed:
        return {
            "ok": False,
            "error": "Invalid GitHub repo URL or owner/repo",
            "detected": {},
            "missing": [],
            "suggestions": [],
        }
    return analyze_repo(parsed[0], parsed[1])


if __name__ == "__main__":
    import sys
    import json
    logging.basicConfig(level=logging.INFO)
    url = sys.argv[1] if len(sys.argv) > 1 else "https://github.com/vercel/next.js"
    result = analyze_repo_url(url)
    print(json.dumps(result, indent=2))
