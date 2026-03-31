# app-auditor

<div align="center">

**[Nometria](https://nometria.com)** takes AI-built apps to production on AWS — secure, scalable, ready for real users.

<sub><i>Before deploying any app, we audit the tech stack and surface production-readiness issues. This is the tool we use internally -- now open source.</i></sub>

[![Deploy with Nometria](https://img.shields.io/badge/Deploy%20with-Nometria-111827?style=for-the-badge)](https://nometria.com)

</div>

---

> Detect tech stack and surface production-readiness issues from any live URL or GitHub repo. One command, zero config.

---

## Quick start

```bash
# Clone and install
git clone https://github.com/nometria/app-auditor
cd app-auditor
pip install -e .

# Audit a live URL
app-audit url https://vercel.com

# Audit a GitHub repo
app-audit repo myorg/myrepo

# JSON output
app-audit url https://myapp.com --format json
```

---

## Usage

### Audit a live URL

```bash
app-audit url https://myapp.com

# JSON output
app-audit url https://myapp.com --format json
```

Output:
```
URL: https://myapp.com
Title: My App
Stack: nextjs, react, supabase

Risks:
  • Supabase client: verify auth flow, RLS, and env key exposure in client.
  • Hosting on Vercel/Netlify: ensure env vars and serverless limits are documented.
```

### Audit a GitHub repo

```bash
app-audit repo github.com/myorg/myrepo
# or shorthand
app-audit repo myorg/myrepo
```

Output:
```
Repo: myorg/myrepo
Detected: vite, react, supabase

Missing:
  ⚠ No Dockerfile found — containerization recommended for production.
  ⚠ No GitHub Actions workflows — consider adding CI/CD.

Suggestions:
  → Vite SPA: add Dockerfile and ensure server rewrite rules for SPA routing.
  → Supabase: verify RLS, auth flow, and env key exposure in client.
```

### Set GitHub token to avoid rate limiting

```bash
export GITHUB_TOKEN=ghp_...
app-audit repo myorg/myrepo
```

---

## Use as a library

```python
from app_auditor import audit_url, analyze_repo_url

# Website audit
result = audit_url("https://myapp.com")
print(result["detected_stack"])  # {"nextjs": True, "react": True, ...}
print(result["risks"])           # ["Supabase client: verify RLS...", ...]

# GitHub repo audit
result = analyze_repo_url("https://github.com/vercel/next.js")
print(result["detected"])        # {"nextjs": True, "docker": False, ...}
print(result["missing"])         # ["No Dockerfile found..."]
print(result["suggestions"])     # ["Next.js: check output mode..."]
```

---

## Detected stack signals

| Signal | Detection method |
|--------|-----------------|
| Next.js | `__next` in HTML, `_next/` paths, `next.js` in server header |
| Vite | `/assets/` + `modulepreload` in HTML |
| React | `react` / `reactdom` in HTML or `package.json` |
| Vue | `v-bind` or `vue` in HTML |
| Supabase | `supabase` in HTML or repo file paths |
| Vercel | `vercel` in HTML, server header, or `vercel.json` |
| Netlify | `netlify` in HTML, header, or config files |
| Docker | `Dockerfile` in repo tree |
| GitHub Actions | `.github/workflows/` in repo tree |

---

## Commercial viability

- Free tier: CLI and library (open source)
- Paid: API with bulk auditing, team dashboards, Slack notifications
- Inbound funnel: developers debugging production issues → upgrade path to managed services

---

## Example output

### `app-audit url https://vercel.com`

```
URL: https://vercel.com/
Title: Vercel: Build and deploy the best web experiences with the AI Cloud
Stack: nextjs, react, vercel

Risks:
  • Hosting on Vercel/Netlify: ensure env vars and serverless limits are documented.
```

### `app-audit url https://supabase.com`

```
URL: https://supabase.com/
Title: Supabase | The Postgres Development Platform.
Stack: nextjs, react, vue, supabase, vercel

Risks:
  • Supabase client: verify auth flow, RLS, and env key exposure in client.
  • Hosting on Vercel/Netlify: ensure env vars and serverless limits are documented.
```

---

<p align="center">Made with ❤️ by <a href="https://nometria.com">Nometria</a> — deploy AI apps to production in one click</p>
