#!/usr/bin/env python3
"""Update the organization profile README with live stats from the GitHub API."""

import os
import re

import requests

ORG = "alphaonelabs"
README_PATH = "profile/README.md"

STATS_START = "<!-- STATS_START -->"
STATS_END = "<!-- STATS_END -->"
REPOS_START = "<!-- REPOS_START -->"
REPOS_END = "<!-- REPOS_END -->"
PROJECTS_BADGE_START = "<!-- PROJECTS_BADGE -->"
PROJECTS_BADGE_END = "<!-- PROJECTS_BADGE_END -->"


def fetch_org_data():
    token = os.environ.get("GITHUB_TOKEN")
    headers = {"Authorization": f"token {token}"} if token else {}

    # Fetch all public repositories
    repos = []
    page = 1
    while True:
        url = (
            f"https://api.github.com/orgs/{ORG}/repos"
            f"?per_page=100&page={page}&type=public"
        )
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if not data:
            break
        repos.extend(data)
        page += 1

    total_stars = sum(r.get("stargazers_count", 0) for r in repos)

    # Use the Search API for accurate open-issue and open-PR counts
    def search_count(query, hdrs):
        url = f"https://api.github.com/search/issues?q={query}&per_page=1"
        resp = requests.get(url, headers=hdrs, timeout=30)
        resp.raise_for_status()
        return resp.json().get("total_count", 0)

    def fetch_counts_by_repo(query, hdrs):
        """Fetch all search results and return counts grouped by repo name."""
        counts = {}
        page = 1
        while True:
            url = f"https://api.github.com/search/issues?q={query}&per_page=100&page={page}"
            resp = requests.get(url, headers=hdrs, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            items = data.get("items", [])
            if not items:
                break
            for item in items:
                repo_url = item.get("repository_url", "")
                repo_name = repo_url.split("/")[-1]
                counts[repo_name] = counts.get(repo_name, 0) + 1
            # GitHub Search API caps at 1 000 results (10 pages × 100)
            if len(items) < 100 or page >= 10:
                break
            page += 1
        return counts

    total_prs = search_count(f"org:{ORG}+type:pr+state:open", headers)
    total_issues = search_count(f"org:{ORG}+type:issue+state:open", headers)

    pr_counts = fetch_counts_by_repo(f"org:{ORG}+type:pr+state:open", headers)
    issue_counts = fetch_counts_by_repo(f"org:{ORG}+type:issue+state:open", headers)

    for repo in repos:
        name = repo.get("name", "")
        repo["open_pr_count"] = pr_counts.get(name, 0)
        repo["open_issue_count"] = issue_counts.get(name, 0)

    return {
        "stars": total_stars,
        "prs": total_prs,
        "issues": total_issues,
        "repos": len(repos),
        "repo_list": sorted(repos, key=lambda r: r.get("stargazers_count", 0), reverse=True),
    }


def build_stats_block(stats):
    stars_badge = (
        f"[![Total Stars](https://img.shields.io/badge/Total%20Stars-{stats['stars']}"
        f"-yellow?style=flat-square&logo=github)](https://github.com/alphaonelabs)"
    )
    prs_badge = (
        f"[![Open PRs](https://img.shields.io/badge/Open%20PRs-{stats['prs']}"
        f"-blue?style=flat-square&logo=github)]"
        f"(https://github.com/pulls?q=is%3Aopen+is%3Apr+user%3Aalphaonelabs)"
    )
    issues_badge = (
        f"[![Open Issues](https://img.shields.io/badge/Open%20Issues-{stats['issues']}"
        f"-red?style=flat-square&logo=github)]"
        f"(https://github.com/issues?q=is%3Aopen+is%3Aissue+user%3Aalphaonelabs)"
    )
    repos_badge = (
        f"[![Public Repos](https://img.shields.io/badge/Public%20Repositories-{stats['repos']}"
        f"-blue?style=flat-square)]"
        f"(https://github.com/orgs/alphaonelabs/repositories)"
    )
    lines = [
        STATS_START,
        "",
        f"{stars_badge} {prs_badge} {issues_badge} {repos_badge}",
        "",
        STATS_END,
    ]
    return "\n".join(lines)


def build_repos_table(repos):
    rows = []
    for repo in repos:
        name = repo.get("name", "")
        url = repo.get("html_url", f"https://github.com/{ORG}/{name}")
        description = (repo.get("description") or "").replace("|", "\\|")
        language = repo.get("language") or "N/A"
        stars = repo.get("stargazers_count", 0)
        forks = repo.get("forks_count", 0)
        open_prs = repo.get("open_pr_count", 0)
        open_issues = repo.get("open_issue_count", 0)
        rows.append(
            f"| [{name}]({url}) | {description} | {language} | ⭐ {stars} | 🍴 {forks} | 🔀 {open_prs} | 🐛 {open_issues} |"
        )

    lines = [
        REPOS_START,
        "",
        "| Repository | Description | Language | Stars | Forks | Open PRs | Open Issues |",
        "|---|---|---|---|---|---|---|",
    ] + rows + [
        "",
        REPOS_END,
    ]
    return "\n".join(lines)


def build_projects_badge(repo_count):
    badge = (
        f"[![Projects](https://img.shields.io/badge/Projects-{repo_count}"
        f"-green?style=for-the-badge)](https://github.com/orgs/alphaonelabs/repositories)"
    )
    return f"{PROJECTS_BADGE_START}\n{badge}\n{PROJECTS_BADGE_END}"


def update_readme(stats):
    with open(README_PATH, "r", encoding="utf-8") as fh:
        content = fh.read()

    # Update stats block
    stats_block = build_stats_block(stats)
    if STATS_START in content:
        pattern = re.escape(STATS_START) + r".*?" + re.escape(STATS_END)
        content = re.sub(pattern, stats_block, content, flags=re.DOTALL)
    else:
        # Fallback: replace the legacy static badges block introduced before
        # STATS markers were added.  Can be removed once all environments have
        # been updated to include the markers.
        legacy = (
            "![Repos](https://img.shields.io/badge/Public%20Repositories-7-blue?style=flat-square)\n"
            "![Contributors](https://img.shields.io/badge/Contributors-Growing-brightgreen?style=flat-square)\n"
            "![Open Source](https://img.shields.io/badge/License-Open%20Source-orange?style=flat-square)"
        )
        content = content.replace(legacy, stats_block)

    # Update repositories table
    repos_block = build_repos_table(stats["repo_list"])
    if REPOS_START in content:
        pattern = re.escape(REPOS_START) + r".*?" + re.escape(REPOS_END)
        content = re.sub(pattern, repos_block, content, flags=re.DOTALL)

    # Update Projects badge in header
    projects_badge = build_projects_badge(stats["repos"])
    if PROJECTS_BADGE_START in content:
        pattern = re.escape(PROJECTS_BADGE_START) + r".*?" + re.escape(PROJECTS_BADGE_END)
        content = re.sub(pattern, projects_badge, content, flags=re.DOTALL)

    with open(README_PATH, "w", encoding="utf-8") as fh:
        fh.write(content)

    print(
        f"README updated — stars: {stats['stars']}, PRs: {stats['prs']}, "
        f"issues: {stats['issues']}, repos: {stats['repos']}"
    )


if __name__ == "__main__":
    stats = fetch_org_data()
    update_readme(stats)
