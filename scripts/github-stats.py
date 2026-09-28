#!/usr/bin/env python3
"""Write assets/github.json for the "Proof of work" section.

Runs nightly in GitHub Actions (and works locally with GITHUB_TOKEN set).
Only public, non-fork repos are named on the page; private work shows up
as contribution counts, never as repo names or commit messages.
"""
import json
import os
import sys
import urllib.request

USER = "adityarya24"
OUT = os.path.join(os.path.dirname(__file__), "..", "assets", "github.json")

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount contributionLevel } }
      }
    }
    pullRequests(states: MERGED) { totalCount }
    repositories(privacy: PUBLIC, ownerAffiliations: OWNER, isFork: false,
                 first: 20, orderBy: {field: PUSHED_AT, direction: DESC}) {
      totalCount
      nodes {
        name
        url
        defaultBranchRef {
          target { ... on Commit { history(first: 10) { nodes { messageHeadline committedDate url } } } }
        }
      }
    }
  }
}
"""

LEVELS = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2, "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}


def fetch():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        sys.exit("GITHUB_TOKEN is not set")
    body = json.dumps({"query": QUERY, "variables": {"login": USER}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    if data.get("errors"):
        sys.exit(f"GraphQL error: {data['errors']}")
    return data["data"]["user"]


def build(user):
    cal = user["contributionsCollection"]["contributionCalendar"]
    weeks = [[LEVELS[d["contributionLevel"]] for d in w["contributionDays"]] for w in cal["weeks"]]
    recent = []
    for repo in user["repositories"]["nodes"]:
        if repo["name"] == f"{USER}.github.io" or repo["name"] == USER:
            continue  # the site and profile repos aren't projects
        ref = repo["defaultBranchRef"]
        commits = ref and [c for c in ref["target"]["history"]["nodes"]
                           if not c["messageHeadline"].startswith("Merge ")]
        if commits:
            c = commits[0]  # newest commit that says what changed
            recent.append({"repo": repo["name"], "message": c["messageHeadline"],
                           "date": c["committedDate"], "url": c["url"]})
    recent.sort(key=lambda c: c["date"], reverse=True)
    return {
        "contributions": cal["totalContributions"],
        "first_day": cal["weeks"][0]["contributionDays"][0]["date"],
        "merged_prs": user["pullRequests"]["totalCount"],
        "public_repos": user["repositories"]["totalCount"],
        "weeks": weeks,
        "recent": recent[:5],
    }


if __name__ == "__main__":
    stats = build(fetch())
    with open(OUT, "w") as f:
        json.dump(stats, f, separators=(",", ":"))
    print(f"{stats['contributions']} contributions, {stats['merged_prs']} merged PRs, "
          f"{stats['public_repos']} public repos, {len(stats['recent'])} recent commits")
