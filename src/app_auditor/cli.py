#!/usr/bin/env python3
"""
app-auditor CLI

Commands:
  app-audit url <url>     Audit a website URL (stack detection + production risks)
  app-audit repo <url>    Audit a GitHub repo (structure, missing files, suggestions)
"""
import argparse
import json
import logging
import sys


def main():
    parser = argparse.ArgumentParser(
        prog="app-audit",
        description="Detect tech stack and surface production-readiness issues.",
    )
    parser.add_argument(
        "command",
        choices=["url", "repo"],
        help="What to audit: a live URL or a GitHub repo",
    )
    parser.add_argument("target", help="URL or GitHub repo (owner/repo or full URL)")
    parser.add_argument(
        "--format",
        choices=["json", "text"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Debug logging")

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.WARNING)

    if args.command == "url":
        from .website_auditor import audit_url
        result = audit_url(args.target)
    else:
        from .github_auditor import analyze_repo_url
        result = analyze_repo_url(args.target)

    if args.format == "json":
        print(json.dumps(result, indent=2))
        return

    # Human-readable text output
    if not result.get("ok"):
        print(f"ERROR: {result.get('error', 'Unknown error')}", file=sys.stderr)
        sys.exit(1)

    if args.command == "url":
        print(f"\nURL: {result['url']}")
        print(f"Title: {result.get('title') or '(none)'}")
        stack = [k for k, v in result.get("detected_stack", {}).items() if v]
        print(f"Stack: {', '.join(stack) or 'unknown'}")
        print("\nRisks:")
        for r in result.get("risks", []):
            print(f"  • {r}")
    else:
        print(f"\nRepo: {result.get('owner')}/{result.get('repo')}")
        if result.get("grade"):
            print(f"Readiness: {result['grade']} ({result.get('score')}/100)"
                  f" · {result.get('file_count', 0)} files")
        langs = result.get("languages") or {}
        if langs:
            top = ", ".join(f"{k} ({v})" for k, v in list(langs.items())[:5])
            print(f"Languages: {top}")
        detected = [k for k, v in result.get("detected", {}).items() if v]
        print(f"Detected: {', '.join(detected) or 'nothing notable'}")
        if result.get("missing"):
            print("\nMissing:")
            for m in result["missing"]:
                print(f"  ⚠ {m}")
        if result.get("suggestions"):
            print("\nSuggestions:")
            for s in result["suggestions"]:
                print(f"  → {s}")


if __name__ == "__main__":
    main()
