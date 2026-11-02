from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from config import AppConfig
from github_client import GitHubClient
from marker_client import MarkerClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _configure_tk_runtime() -> None:
    """Provide Tcl/Tk resources when Python is running from a virtual environment or bundled app."""
    if getattr(sys, "frozen", False):
        runtime_root = Path(sys._MEIPASS) / "tk_runtime"
    else:
        runtime_root = Path(__file__).resolve().parent / ".tk-runtime"

    tcl_library = runtime_root / "tcl_library"
    tk_library = runtime_root / "tk_library"
    if tcl_library.is_dir() and tk_library.is_dir():
        os.environ["TCL_LIBRARY"] = str(tcl_library)
        os.environ["TK_LIBRARY"] = str(tk_library)


@dataclass
class SyncAction:
    kind: str
    marker_id: str
    title: str
    body: str
    target_state: str
    issue_number: int | None = None
    changes: Dict[str, str | None] | None = None


class MarkerGitHubBridge:
    def __init__(self, config: AppConfig):
        self.config = config
        self.marker_client = MarkerClient(
            base_url=config.marker.base_url,
            tasks_url=config.marker.tasks_url,
            workspace_id=config.marker.workspace_id,
            api_key=config.marker.api_key,
            cookie=config.marker.cookie,
            auth_mode=config.marker.auth_mode,
        )
        self.github_client = GitHubClient(
            owner=config.github.owner,
            repo=config.github.repo,
            token=config.github.token,
            api_url=config.github.api_url,
            label=config.github.label,
        )

    def sync(self) -> Dict[str, Any]:
        logger.info("Consultando tareas de Marker.io...")
        tasks = self.marker_client.get_tasks()
        logger.info("Se encontraron %s tareas", len(tasks))

        skipped = 0
        actions: List[SyncAction] = []
        for task in tasks:
            marker_id = str(task.get("id") or "").strip()
            if not marker_id:
                logger.warning("Tarea sin id, se omite: %s", task)
                continue

            marker_state = str(task.get("status") or "").strip().lower()
            should_close = marker_state in {"closed", "archived"}
            target_state = "closed" if should_close else "open"
            title = f"[{task.get('status','unknown')}] {task.get('title') or 'Tarea Marker.io'}"
            body = self.github_client.build_issue_body(task)
            existing = self.github_client.issue_exists_for_marker_id(marker_id)
            if existing:
                changes = {
                    "title": title if existing.get("title") != title else None,
                    "body": body if (existing.get("body") or "") != body else None,
                    "state": target_state if existing.get("state") != target_state else None,
                }
                if any(value is not None for value in changes.values()):
                    actions.append(SyncAction("update", marker_id, title, body, target_state, existing["number"], changes))
                else:
                    logger.info("Sin cambios para marker_id=%s (#%s)", marker_id, existing.get("number"))
                    skipped += 1
                continue

            actions.append(SyncAction("create", marker_id, title, body, target_state))

        planned_created = sum(action.kind == "create" for action in actions)
        planned_updated = sum(action.kind == "update" for action in actions)

        if self.config.dry_run:
            for action in actions:
                if action.kind == "create":
                    verb = "crear y cerrar" if action.target_state == "closed" else "crear"
                    logger.info("DRY RUN: %s issue para marker_id=%s => %s", verb, action.marker_id, action.title)
                else:
                    logger.info("DRY RUN: actualizar issue existente #%s para marker_id=%s", action.issue_number, action.marker_id)
            return self._result(
                len(tasks),
                planned_created,
                planned_updated,
                skipped,
                dry_run=True,
                planned_created=planned_created,
                planned_updated=planned_updated,
            )

        if self.config.require_confirmation and actions:
            selected_actions = self._confirm_actions(actions)
            if selected_actions is None:
                logger.info("Sincronización cancelada por el usuario.")
                return self._result(len(tasks), 0, 0, skipped, cancelled=True, planned_created=planned_created, planned_updated=planned_updated)
            actions = selected_actions
            planned_created = sum(action.kind == "create" for action in actions)
            planned_updated = sum(action.kind == "update" for action in actions)

        created = 0
        updated = 0
        for action in actions:
            if action.kind == "create":
                issue = self.github_client.create_issue(title=action.title, body=action.body)
                if action.target_state == "closed":
                    self.github_client.close_issue(issue["number"])
                logger.info("Issue creada: #%s para marker_id=%s", issue.get("number"), action.marker_id)
                created += 1
            else:
                self.github_client.update_issue(action.issue_number, **(action.changes or {}))
                logger.info("Issue actualizada: #%s para marker_id=%s", action.issue_number, action.marker_id)
                updated += 1

        return self._result(len(tasks), created, updated, skipped)

    @staticmethod
    def _result(tasks_found: int, created: int, updated: int, skipped: int, *, dry_run: bool = False, cancelled: bool = False, planned_created: int = 0, planned_updated: int = 0) -> Dict[str, Any]:
        return {
            "tasks_found": tasks_found,
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "dry_run": dry_run,
            "cancelled": cancelled,
            "planned_created": planned_created,
            "planned_updated": planned_updated,
        }

    @staticmethod
    def _confirm_actions(actions: List[SyncAction]) -> List[SyncAction] | None:
        _configure_tk_runtime()
        import tkinter as tk
        from tkinter import ttk

        root = tk.Tk()

        root.title("Marker.io → GitHub: Confirm Changes")
        root.geometry("960x560")
        root.minsize(720, 380)
        root.configure(bg="#0d1117")

        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("Bridge.Treeview", background="#161b22", fieldbackground="#161b22", foreground="#f0f6fc", rowheight=28, bordercolor="#30363d")
        style.configure("Bridge.Treeview.Heading", background="#21262d", foreground="#f0f6fc", relief="flat")
        style.map("Bridge.Treeview.Heading", background=[("active", "#30363d")])
        style.configure("Bridge.TButton", background="#238636", foreground="#ffffff", borderwidth=0, padding=(12, 7))
        style.map("Bridge.TButton", background=[("active", "#2ea043")])

        created = sum(action.kind == "create" for action in actions)
        updated = len(actions) - created
        tk.Label(root, text=f"Pending changes: {created} new · {updated} updates", font=("Segoe UI", 11, "bold"), fg="#f0f6fc", bg="#0d1117").pack(padx=16, pady=(16, 8), anchor="w")
        tk.Label(root, text="Uncheck any task you do not want to send to GitHub, then select Apply Changes.", fg="#8b949e", bg="#0d1117").pack(padx=16, pady=(0, 12), anchor="w")

        frame = tk.Frame(root, bg="#0d1117")
        frame.pack(fill="both", expand=True, padx=16, pady=4)
        columns = ("selected", "action", "issue", "state", "title")
        tree = ttk.Treeview(frame, columns=columns, show="headings", style="Bridge.Treeview")
        for column, heading, width in (("selected", "Include", 75), ("action", "Action", 120), ("issue", "Issue", 90), ("state", "State", 90), ("title", "Title", 525)):
            tree.heading(column, text=heading)
            tree.column(column, width=width, anchor="w")
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        selected_items: Dict[str, bool] = {}
        for action in actions:
            label = "Create" if action.kind == "create" else "Update"
            issue = "New" if action.issue_number is None else f"#{action.issue_number}"
            item = tree.insert("", "end", values=("☑", label, issue, action.target_state, action.title))
            selected_items[item] = True

        def toggle_selection(event: Any) -> str | None:
            if tree.identify_region(event.x, event.y) != "cell" or tree.identify_column(event.x) != "#1":
                return None
            item = tree.identify_row(event.y)
            if not item:
                return None
            selected_items[item] = not selected_items[item]
            values = list(tree.item(item, "values"))
            values[0] = "☑" if selected_items[item] else "☐"
            tree.item(item, values=values)
            return "break"

        tree.bind("<Button-1>", toggle_selection)

        def set_all_selected(selected: bool) -> None:
            for item in tree.get_children():
                selected_items[item] = selected
                values = list(tree.item(item, "values"))
                values[0] = "☑" if selected else "☐"
                tree.item(item, values=values)

        decision: Dict[str, Any] = {"confirmed": False, "selected_actions": []}

        def confirm() -> None:
            decision["selected_actions"] = [
                action
                for item, action in zip(tree.get_children(), actions)
                if selected_items[item]
            ]
            decision["confirmed"] = True
            root.destroy()

        buttons = tk.Frame(root, bg="#0d1117")
        buttons.pack(fill="x", padx=16, pady=16)
        ttk.Button(buttons, text="Select All", command=lambda: set_all_selected(True)).pack(side="left")
        ttk.Button(buttons, text="Clear All", command=lambda: set_all_selected(False)).pack(side="left", padx=(8, 0))
        ttk.Button(buttons, text="Cancel", command=root.destroy).pack(side="right")
        ttk.Button(buttons, text="Apply Changes", command=confirm, style="Bridge.TButton").pack(side="right", padx=(0, 8))
        root.protocol("WM_DELETE_WINDOW", root.destroy)
        root.mainloop()
        if not decision["confirmed"]:
            return None
        return decision["selected_actions"]

def main() -> int:
    try:
        config = AppConfig.from_env()
        bridge = MarkerGitHubBridge(config)
        result = bridge.sync()
        print(result)
        return 0
    except Exception as exc:
        logger.exception("Error durante la sincronización: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
