from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests


class MarkerClient:
    def __init__(self, base_url: str, tasks_url: Optional[str], workspace_id: Optional[str], api_key: Optional[str], cookie: Optional[str], auth_mode: str = "api_key"):
        self.base_url = base_url.rstrip("/")
        self.tasks_url = (tasks_url or "").strip() or None
        self.workspace_id = (workspace_id or "").strip() or None
        self.api_key = (api_key or "").strip() or None
        self.cookie = (cookie or "").strip() or None
        self.auth_mode = (auth_mode or "api_key").strip().lower()

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/json",
            "User-Agent": "markerio-github-bridge/1.0",
        }

        if self.auth_mode == "api_key" and self.api_key:
            headers["X-Api-Key"] = self.api_key
        elif self.auth_mode == "cookie" and self.cookie:
            headers["Cookie"] = self.cookie

        return headers

    def _get_tasks_endpoint(self) -> str:
        if self.tasks_url:
            return self.tasks_url

        if self.workspace_id:
            return f"{self.base_url}/v1/workspaces/{self.workspace_id}/issues"

        return f"{self.base_url}/v1/issues"

    def fetch_tasks(self) -> List[Dict[str, Any]]:
        endpoint = self._get_tasks_endpoint()
        payload = self._get_json(endpoint)
        tasks = self._extract_tasks(payload, endpoint)

        if not isinstance(payload, dict):
            return tasks

        total = payload.get("total")
        limit = payload.get("limit")
        offset = payload.get("offset", 0)
        if not all(isinstance(value, int) for value in (total, limit, offset)) or limit <= 0:
            return tasks

        next_offset = offset + len(tasks)
        while next_offset < total:
            page_endpoint = self._set_query_parameter(endpoint, "offset", next_offset)
            page_payload = self._get_json(page_endpoint)
            page_tasks = self._extract_tasks(page_payload, page_endpoint)
            if not page_tasks:
                break

            tasks.extend(page_tasks)
            next_offset += len(page_tasks)

        return tasks

    def _get_json(self, endpoint: str) -> Any:
        response = requests.get(endpoint, headers=self._headers(), timeout=30)
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _set_query_parameter(endpoint: str, name: str, value: int) -> str:
        parsed = urlsplit(endpoint)
        query = [(key, item) for key, item in parse_qsl(parsed.query, keep_blank_values=True) if key != name]
        query.append((name, str(value)))
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment))

    @staticmethod
    def _extract_tasks(payload: Any, endpoint: str) -> List[Dict[str, Any]]:
        if isinstance(payload, list):
            return payload

        if isinstance(payload, dict):
            for key in ("tasks", "issues", "data", "results"):
                value = payload.get(key)
                if isinstance(value, list):
                    return value
                if isinstance(value, dict):
                    nested = value.get("tasks") or value.get("issues") or value.get("data")
                    if isinstance(nested, list):
                        return nested

        raise ValueError(f"La respuesta de Marker no tenía una lista de tareas en {endpoint}")

    def normalize_task(self, item: Dict[str, Any]) -> Dict[str, Any]:
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        project = item.get("project") if isinstance(item.get("project"), dict) else {}
        return {
            "id": str(item.get("id") or item.get("uuid") or item.get("issue_id") or item.get("marker_id") or "").strip(),
            "title": str(item.get("title") or item.get("name") or item.get("summary") or "Sin título").strip(),
            "status": str(item.get("state") or item.get("status") or "unknown").strip(),
            "url": (item.get("url") or item.get("webUrl") or item.get("publicUrl") or item.get("privateUrl") or "").strip(),
            "project_id": str(item.get("project_id") or item.get("projectId") or project.get("id") or item.get("workspace_id") or "").strip(),
            "project_name": str(item.get("project_name") or item.get("projectName") or project.get("name") or item.get("workspace_name") or "").strip(),
            "description": str(item.get("description") or metadata.get("description") or "").strip(),
            "created_at": item.get("createdAt") or item.get("created_at"),
            "updated_at": item.get("updatedAt") or item.get("updated_at"),
            "closed_at": item.get("closedAt") or item.get("archivedAt") or item.get("closed_at"),
        }

    def get_tasks(self) -> List[Dict[str, Any]]:
        raw_tasks = self.fetch_tasks()
        return [self.normalize_task(task) for task in raw_tasks if str(task.get("id") or task.get("uuid") or task.get("issue_id") or task.get("marker_id") or "").strip()]
