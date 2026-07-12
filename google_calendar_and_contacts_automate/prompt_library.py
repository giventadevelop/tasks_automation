"""Prompt library window — tabbed snippets with one-click clipboard copy.

Persists custom tabs/prompts under %LOCALAPPDATA%\\tasks_automation\\prompt_library.json.
"""
from __future__ import annotations

import json
import os
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Any


_STATUS_DIR = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
    "tasks_automation",
)
PROMPTS_FILE = os.environ.get(
    "TASKS_PROMPT_LIBRARY",
    os.path.join(_STATUS_DIR, "prompt_library.json"),
)

# Built-in starter tabs (merged on first run; user edits are preserved thereafter).
DEFAULT_LIBRARY: dict[str, Any] = {
    "version": 1,
    "tabs": [
        {
            "id": "java_job_search",
            "title": "Java Job Search",
            "prompts": [
                {
                    "label": "Junk → jobs_2026 (comprehensive)",
                    "text": (
                        "Check my Outlook.com Junk Email folder for Java jobs and move "
                        "matching emails into the jobs_2026 folder. Include: Java / J2EE / "
                        "Spring Boot / microservices roles in NJ or NY; ANY remote Java roles; "
                        "and Java Architect roles regardless of location. Also include "
                        "interview / assessment / RTR emails tied to those Java roles. "
                        "Exclude .NET, React-only, Angular-only, and onsite-only roles outside "
                        "NJ/NY. Bulk-move matches to jobs_2026."
                    ),
                },
            ],
        },
        {
            "id": "cursor_update",
            "title": "Cursor Update",
            "prompts": [
                {
                    "label": "Update Cursor — HP Omen",
                    "text": "Update cursor with the latest for this PC HP Omen",
                },
                {
                    "label": "Update Cursor — HP ZBook-17",
                    "text": "Update cursor with the latest for this PC HP ZBook-17",
                },
                {
                    "label": "Update Cursor — this machine (auto-detect)",
                    "text": (
                        "Update Cursor to the latest version on this PC — detect the "
                        "machine and architecture, then install."
                    ),
                },
            ],
        },
    ],
}


def _ensure_dir() -> None:
    os.makedirs(_STATUS_DIR, exist_ok=True)


def load_library() -> dict[str, Any]:
    _ensure_dir()
    if not os.path.isfile(PROMPTS_FILE):
        save_library(DEFAULT_LIBRARY)
        return json.loads(json.dumps(DEFAULT_LIBRARY))
    try:
        with open(PROMPTS_FILE, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or "tabs" not in data:
            return json.loads(json.dumps(DEFAULT_LIBRARY))
        return data
    except (OSError, json.JSONDecodeError):
        return json.loads(json.dumps(DEFAULT_LIBRARY))


def save_library(data: dict[str, Any]) -> None:
    _ensure_dir()
    with open(PROMPTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def _slug(title: str) -> str:
    base = "".join(c if c.isalnum() or c in "-_" else "_" for c in title.strip().lower())
    return base[:40] or "tab"


def _copy_to_clipboard(widget: tk.Misc, text: str) -> None:
    widget.clipboard_clear()
    widget.clipboard_append(text)
    widget.update()


def show_prompt_library(parent: tk.Misc | None = None) -> None:
    """Open the multi-tab prompt library (modal)."""
    library = load_library()

    own_root = parent is None
    if own_root:
        root = tk.Tk()
        root.withdraw()
        win = tk.Toplevel(root)
    else:
        root = None
        win = tk.Toplevel(parent)

    win.title("Prompt Library")
    win.configure(bg="#ecf0f1")
    win.minsize(560, 420)

    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    w, h = min(720, int(sw * 0.55)), min(560, int(sh * 0.7))
    win.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

    header = tk.Frame(win, bg="#2c3e50", height=44)
    header.pack(fill="x")
    header.pack_propagate(False)
    tk.Label(
        header,
        text="Prompt Library — copy into Cursor chat",
        fg="white",
        bg="#2c3e50",
        font=("Helvetica", 13, "bold"),
    ).pack(pady=10)

    body = tk.Frame(win, bg="#ecf0f1", padx=12, pady=10)
    body.pack(fill="both", expand=True)

    notebook = ttk.Notebook(body)
    notebook.pack(fill="both", expand=True)

    status_var = tk.StringVar(value="Click Copy to put a prompt on the clipboard.")

    def flash_status(msg: str) -> None:
        status_var.set(msg)
        win.after(2500, lambda: status_var.set("Click Copy to put a prompt on the clipboard."))

    def rebuild_tabs() -> None:
        for tab_id in notebook.tabs():
            notebook.forget(tab_id)
        for tab in library.get("tabs", []):
            _build_tab(tab)

    def _build_tab(tab: dict[str, Any]) -> None:
        frame = tk.Frame(notebook, bg="#ecf0f1")
        notebook.add(frame, text=tab.get("title") or "Tab")

        canvas = tk.Canvas(frame, bg="#ecf0f1", highlightthickness=0)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg="#ecf0f1")

        inner.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        prompts = tab.get("prompts") or []
        if not prompts:
            tk.Label(
                inner,
                text="No prompts yet — use “Add prompt to this tab”.",
                bg="#ecf0f1",
                font=("Helvetica", 10),
                fg="#7f8c8d",
            ).pack(anchor="w", padx=8, pady=16)

        for i, prompt in enumerate(prompts):
            card = tk.Frame(
                inner,
                bg="white",
                highlightbackground="#bdc3c7",
                highlightthickness=1,
                padx=10,
                pady=8,
            )
            card.pack(fill="x", padx=8, pady=6)

            label = (prompt.get("label") or f"Prompt {i + 1}").strip()
            text = (prompt.get("text") or "").strip()

            tk.Label(
                card,
                text=label,
                bg="white",
                font=("Helvetica", 10, "bold"),
                anchor="w",
            ).pack(fill="x")

            text_box = tk.Text(
                card,
                height=min(5, max(2, text.count("\n") + 2)),
                wrap="word",
                font=("Consolas", 10),
                relief="flat",
                bg="#f8f9fa",
            )
            text_box.insert("1.0", text)
            text_box.configure(state="disabled")
            text_box.pack(fill="x", pady=(4, 6))

            btn_row = tk.Frame(card, bg="white")
            btn_row.pack(fill="x")

            def make_copy(t: str = text, lbl: str = label):
                def _copy() -> None:
                    _copy_to_clipboard(win, t)
                    flash_status(f"Copied: {lbl}")

                return _copy

            tk.Button(
                btn_row,
                text="Copy",
                width=10,
                bg="#3498db",
                fg="white",
                activebackground="#2980b9",
                command=make_copy(),
            ).pack(side="left")

            def make_delete(tab_ref: dict = tab, idx: int = i):
                def _delete() -> None:
                    if not messagebox.askyesno(
                        "Delete prompt",
                        f"Remove this prompt from “{tab_ref.get('title')}”?",
                        parent=win,
                    ):
                        return
                    tab_ref["prompts"].pop(idx)
                    save_library(library)
                    rebuild_tabs()
                    flash_status("Prompt removed.")

                return _delete

            tk.Button(
                btn_row,
                text="Delete",
                width=8,
                bg="#e74c3c",
                fg="white",
                activebackground="#c0392b",
                command=make_delete(),
            ).pack(side="left", padx=(8, 0))

        add_row = tk.Frame(inner, bg="#ecf0f1")
        add_row.pack(fill="x", padx=8, pady=(8, 12))

        def add_prompt_to_tab(tab_ref: dict = tab) -> None:
            label = simpledialog.askstring(
                "New prompt",
                "Short label (shown above the prompt):",
                parent=win,
            )
            if not label or not label.strip():
                return
            text = simpledialog.askstring(
                "New prompt",
                "Prompt text to copy:",
                parent=win,
            )
            if not text or not text.strip():
                return
            tab_ref.setdefault("prompts", []).append(
                {"label": label.strip(), "text": text.strip()}
            )
            save_library(library)
            rebuild_tabs()
            flash_status(f"Added prompt to “{tab_ref.get('title')}”.")

        tk.Button(
            add_row,
            text="+ Add prompt to this tab",
            bg="#27ae60",
            fg="white",
            activebackground="#1e8449",
            command=add_prompt_to_tab,
        ).pack(anchor="w")

    def add_tab() -> None:
        title = simpledialog.askstring(
            "New tab",
            "Tab name (e.g. Laundry, Hermes, Deploy):",
            parent=win,
        )
        if not title or not title.strip():
            return
        title = title.strip()
        existing_ids = {t.get("id") for t in library.get("tabs", [])}
        tab_id = _slug(title)
        n = 1
        while tab_id in existing_ids:
            tab_id = f"{_slug(title)}_{n}"
            n += 1

        first_label = simpledialog.askstring(
            "First prompt",
            "Short label for the first prompt (optional — Cancel to create empty tab):",
            parent=win,
        )
        prompts: list[dict[str, str]] = []
        if first_label and first_label.strip():
            first_text = simpledialog.askstring(
                "First prompt",
                "Prompt text to copy:",
                parent=win,
            )
            if first_text and first_text.strip():
                prompts.append(
                    {"label": first_label.strip(), "text": first_text.strip()}
                )

        library.setdefault("tabs", []).append(
            {"id": tab_id, "title": title, "prompts": prompts}
        )
        save_library(library)
        rebuild_tabs()
        # Select the new last tab
        tabs = notebook.tabs()
        if tabs:
            notebook.select(tabs[-1])
        flash_status(f"Tab “{title}” added.")

    def delete_current_tab() -> None:
        idx = notebook.index(notebook.select()) if notebook.tabs() else -1
        tabs = library.get("tabs") or []
        if idx < 0 or idx >= len(tabs):
            return
        title = tabs[idx].get("title", "this tab")
        if not messagebox.askyesno(
            "Delete tab",
            f"Delete tab “{title}” and all its prompts?",
            parent=win,
        ):
            return
        tabs.pop(idx)
        save_library(library)
        rebuild_tabs()
        flash_status(f"Tab “{title}” deleted.")

    toolbar = tk.Frame(body, bg="#ecf0f1")
    toolbar.pack(fill="x", pady=(8, 0))
    tk.Button(
        toolbar,
        text="+ New tab",
        bg="#8e44ad",
        fg="white",
        activebackground="#7d3c98",
        command=add_tab,
    ).pack(side="left")
    tk.Button(
        toolbar,
        text="Delete current tab",
        bg="#c0392b",
        fg="white",
        activebackground="#922b21",
        command=delete_current_tab,
    ).pack(side="left", padx=(8, 0))
    tk.Button(
        toolbar,
        text="Close",
        width=10,
        command=win.destroy,
    ).pack(side="right")

    status = tk.Label(
        body,
        textvariable=status_var,
        bg="#ecf0f1",
        fg="#34495e",
        font=("Helvetica", 9),
        anchor="w",
    )
    status.pack(fill="x", pady=(6, 0))

    rebuild_tabs()
    win.transient(parent) if parent else None
    win.grab_set()
    win.focus_force()
    win.wait_window()
    if own_root and root is not None:
        try:
            root.destroy()
        except Exception:
            pass
