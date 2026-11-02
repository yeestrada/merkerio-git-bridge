from __future__ import annotations

import argparse
import sys
from typing import Any, Dict, List

from config import GitHubConfig
from github_client import GitHubClient

BRIDGE_FOOTER = "Generated automatically by markerio-github-bridge"


def bridge_issues(client: GitHubClient) -> List[Dict[str, Any]]:
    return [
        issue
        for issue in client.list_issues(state="all")
        if "pull_request" not in issue
        and "marker_id:" in (issue.get("body") or "")
        and BRIDGE_FOOTER in (issue.get("body") or "")
    ]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Lista o elimina únicamente issues creados por markerio-github-bridge."
    )
    parser.add_argument("--delete", action="store_true", help="Elimina permanentemente los issues encontrados.")
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Confirma la eliminación permanente. Obligatorio junto con --delete.",
    )
    args = parser.parse_args()

    config = GitHubConfig.from_env()
    client = GitHubClient(
        owner=config.owner,
        repo=config.repo,
        token=config.token,
        api_url=config.api_url,
        label=config.label,
    )
    issues = bridge_issues(client)

    print(f"Se encontraron {len(issues)} issues creados por el bridge en {config.owner}/{config.repo}.")
    for issue in issues:
        print(f"#{issue['number']} [{issue['state']}] {issue['title']}")

    if not args.delete:
        print("Modo vista previa: no se eliminó nada. Usa --delete --confirm para borrar permanentemente.")
        return 0

    if not args.confirm:
        parser.error("La eliminación requiere --delete --confirm.")

    for issue in issues:
        node_id = issue.get("node_id")
        if not node_id:
            raise RuntimeError(f"El issue #{issue['number']} no tiene node_id; se cancela por seguridad.")
        client.delete_issue(node_id)
        print(f"Eliminado #{issue['number']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
