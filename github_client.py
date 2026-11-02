from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import requests


class GitHubClient:
    def __init__(self, owner: str, repo: str, token: str, api_url: str = "https://api.github.com", label: str = "markerio"):
        self.owner = owner
        self.repo = repo
        self.token = token
        self.api_url = api_url.rstrip("/")
        self.label = label
        self._issues_cache: Optional[List[Dict[str, Any]]] = None

    @property
    def base_headers(self) -> Dict[str, str]:
        return {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def list_issues(self, state: str = "open") -> List[Dict[str, Any]]:
        url = f"{self.api_url}/repos/{self.owner}/{self.repo}/issues"
        issues: List[Dict[str, Any]] = []
        page = 1

        while True:
            params = {"state": state, "per_page": 100, "page": page}
            response = requests.get(url, headers=self.base_headers, params=params, timeout=30)
            response.raise_for_status()
            batch = response.json()
            issues.extend(batch)
            if len(batch) < 100:
                return issues
            page += 1

    def issue_exists_for_marker_id(self, marker_id: str) -> Optional[Dict[str, Any]]:
        if self._issues_cache is None:
            self._issues_cache = self.list_issues(state="all")

        for issue in self._issues_cache:
            body = issue.get("body") or ""
            if f"marker_id: {marker_id}" in body or f"marker-id: {marker_id}" in body:
                return issue
        return None

    def create_issue(self, title: str, body: str) -> Dict[str, Any]:
        url = f"{self.api_url}/repos/{self.owner}/{self.repo}/issues"
        payload = {
            "title": title,
            "body": body,
            "labels": [self.label],
        }
        response = requests.post(url, headers=self.base_headers, data=json.dumps(payload), timeout=30)
        response.raise_for_status()
        return response.json()

    def close_issue(self, issue_number: int) -> Dict[str, Any]:
        return self.update_issue(issue_number, state="closed")

    def update_issue(self, issue_number: int, *, title: Optional[str] = None, body: Optional[str] = None, state: Optional[str] = None) -> Dict[str, Any]:
        payload = {
            key: value
            for key, value in {"title": title, "body": body, "state": state}.items()
            if value is not None
        }
        if not payload:
            raise ValueError("Se requiere al menos un campo para actualizar el issue.")

        url = f"{self.api_url}/repos/{self.owner}/{self.repo}/issues/{issue_number}"
        response = requests.patch(url, headers=self.base_headers, data=json.dumps(payload), timeout=30)
        response.raise_for_status()
        return response.json()

    def delete_issue(self, node_id: str) -> None:
        response = requests.post(
            f"{self.api_url}/graphql",
            headers=self.base_headers,
            json={
                "query": "mutation($issueId: ID!) { deleteIssue(input: {issueId: $issueId}) { repository { id } } }",
                "variables": {"issueId": node_id},
            },
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("errors"):
            raise RuntimeError(f"GitHub rechazó la eliminación: {payload['errors']}")

    def add_label_to_issue(self, issue_number: int) -> None:
        url = f"{self.api_url}/repos/{self.owner}/{self.repo}/issues/{issue_number}/labels"
        payload = [{"name": self.label}]
        requests.post(url, headers=self.base_headers, data=json.dumps(payload), timeout=30)

    def build_issue_body(self, task: Dict[str, Any]) -> str:
        marker_id = task.get("id")
        title = task.get("title") or "Sin título"
        status = task.get("status") or "unknown"
        url = task.get("url") or ""
        project_name = task.get("project_name") or ""
        project_id = task.get("project_id") or ""
        description = task.get("description") or ""
        created_at = task.get("created_at") or ""
        closed_at = task.get("closed_at") or ""

        body = [
            "## Marker.io task",
            f"- marker_id: {marker_id}",
            f"- title: {title}",
            f"- status: {status}",
            f"- project_name: {project_name}",
            f"- project_id: {project_id}",
        ]

        if created_at:
            body.append(f"- marker_created_at: {created_at}")
        if closed_at:
            body.append(f"- marker_closed_at: {closed_at}")

        if url:
            body.append(f"- marker_url: {url}")

        if description:
            body.extend(["", "## Description", str(description)])

        body.append("")
        body.append("Generated automatically by markerio-github-bridge")
        return "\n".join(body)
