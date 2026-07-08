#!/usr/bin/env python3
"""quick_update.py - one-click package update.

Runs the quick package-update workflow either as a GUI or as a CLI.

GUI:
  python quick_update.py

CLI:
  python quick_update.py --project-dir /path/to/project --story-url <ADO story URL>
  python quick_update.py --project-dir /path/to/project --org my-org --project "My Project" --story-id 12345
"""

from __future__ import annotations

import argparse
import os
import sys
import traceback
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from pipeline.stream import Stream
from ui.utils import parse_ado_url


@dataclass
class QuickUpdateConfig:
    project_dir: str
    org: str
    project: str
    story_id: int
    log_dir: str | None = None
    columns: list[str] | None = None
    workers: int = 8
    npm_cmd: str = "npm"
    npm_timeout: int = 90
    npm_registry: str | None = None
    gradle_timeout: int = 30
    skip_block_check: bool = False
    skip_build_validation: bool = False
    auto_open_report: bool = False
    artifactory_source: str = ""
    artifactory_repo: str = "ins-cp-mgmt-gradle-virtual"
    artifactory_username: str = ""
    artifactory_password: str = ""
    package_jsons: list[str] | None = None
    build_files: list[str] | None = None


def _default_columns() -> list:
    return ["title", "description", "description_html"]


def _count_changes(fr: dict, change_type: str) -> int:
    return sum(1 for c in fr.get("display_changes", []) if c.get("change_type") == change_type)


def run_quick_update(cfg: QuickUpdateConfig) -> dict:
    """Run the quick update workflow and return report metadata.

    This is shared by the GUI worker and the CLI entry point.
    """

    from output.gradle import write_gradle_file
    from output.node import write_package_json
    from parsers.gradle_tree import get_gradle_cmd
    from pipeline.ado import fetch_ado_tasks
    from pipeline.gradle import analyze_gradle
    from pipeline.node import analyze_node
    from shared.build_validation import (
        validate_gradle_project_or_rollback,
        validate_node_project_or_rollback,
    )
    from shared.report import generate_task_report
    from ui.utils import scan_for_dep_managers

    proj = os.path.abspath(cfg.project_dir)
    log_dir = cfg.log_dir or os.path.join(proj, "logs")
    columns = cfg.columns or _default_columns()

    dep_managers = []
    for path in cfg.package_jsons or []:
        abs_path = os.path.abspath(path)
        if not os.path.isfile(abs_path):
            raise RuntimeError(f"--package-json file not found: {path}")
        dep_managers.append(
            {
                "type": "node",
                "label": f"Node/npm  >  {os.path.relpath(abs_path, proj)}",
                "file_path": abs_path,
            }
        )
    for path in cfg.build_files or []:
        abs_path = os.path.abspath(path)
        if not os.path.isfile(abs_path):
            raise RuntimeError(f"--build-file file not found: {path}")
        dep_managers.append(
            {
                "type": "gradle",
                "label": f"Gradle    >  {os.path.relpath(abs_path, proj)}",
                "file_path": abs_path,
            }
        )

    if not dep_managers:
        dep_managers = scan_for_dep_managers(proj)

    if not dep_managers:
        raise RuntimeError(
            f"No package.json or build.gradle files found under {proj}. "
            "Pass --project-dir pointing at the target project root, or pass "
            "--package-json /path/to/package.json and/or --build-file /path/to/build.gradle."
        )

    print(f"Found {len(dep_managers)} dependency file(s):")
    for dm in dep_managers:
        print(f"  - {dm['label']}")

    csv_path, ado_tasks = fetch_ado_tasks(
        org=cfg.org,
        project=cfg.project,
        story_id=cfg.story_id,
        log_dir=log_dir,
        csv_columns=["id", "title", "description", "description_html"],
        auth_method="azcli",
        az_login_fallback=True,
    )

    file_results = []
    totals = {
        "npm_direct": 0,
        "npm_override": 0,
        "gradle_direct": 0,
        "gradle_force": 0,
        "skipped": 0,
    }

    for dm in dep_managers:
        file_path = dm["file_path"]
        print("")
        print("-" * 60)
        print(f"Analyze {dm['label']}")
        print("-" * 60)
        print(f"File: {file_path}")

        if dm["type"] == "node":
            fr = analyze_node(
                csv_path=csv_path,
                pkg_json_path=file_path,
                log_dir=log_dir,
                columns=columns,
                npm_cmd=cfg.npm_cmd,
                npm_timeout=cfg.npm_timeout,
                workers=cfg.workers,
                registry=cfg.npm_registry,
                skip_block_check=cfg.skip_block_check,
                xray_host=cfg.artifactory_source,
            )
            fr["dm_type"] = "node"
            fr["file_path"] = file_path

            direct_count = _count_changes(fr, "direct")
            override_count = _count_changes(fr, "override")
            skipped_count = len(fr.get("skipped_display", []))
            totals["npm_direct"] += direct_count
            totals["npm_override"] += override_count
            totals["skipped"] += skipped_count

            print(
                f"Changes: {direct_count} direct, "
                f"{override_count} override(s), {skipped_count} skipped"
            )
            if fr.get("display_changes"):
                print(f"Writing {file_path} in place...")
                with open(file_path, encoding="utf-8") as f:
                    original_text = f.read()
                write_package_json(fr["pkg"], file_path, file_path, in_place=True)
                if cfg.skip_build_validation:
                    print("Build validation skipped.")
                else:
                    validate_node_project_or_rollback(
                        file_path,
                        original_text,
                        npm_cmd=cfg.npm_cmd,
                        timeout=max(cfg.npm_timeout, 600),
                        direct_changes=fr.get("direct_changes", []),
                        override_changes=fr.get("override_changes", []),
                        log_dir=log_dir,
                    )
            else:
                print("Nothing to update for this package.json.")

        elif dm["type"] == "gradle":
            fr = analyze_gradle(
                csv_path=csv_path,
                build_file=file_path,
                log_dir=log_dir,
                columns=columns,
                artifactory_source=cfg.artifactory_source,
                artifactory_repo=cfg.artifactory_repo,
                artifactory_username=cfg.artifactory_username,
                artifactory_password=cfg.artifactory_password,
                workers=cfg.workers,
                gradle_timeout=cfg.gradle_timeout,
                skip_block_check=cfg.skip_block_check,
                xray_host=cfg.artifactory_source,
            )
            fr["dm_type"] = "gradle"
            fr["file_path"] = file_path

            gradle_count = _count_changes(fr, "gradle")
            force_count = _count_changes(fr, "gradle-force")
            skipped_count = len(fr.get("skipped_display", []))
            totals["gradle_direct"] += gradle_count
            totals["gradle_force"] += force_count
            totals["skipped"] += skipped_count

            print(
                f"Changes: {gradle_count} Gradle direct, "
                f"{force_count} force(s), {skipped_count} skipped"
            )
            if fr.get("changes") or fr.get("force_entries"):
                print(f"Writing {file_path} in place...")
                write_gradle_file(
                    fr["build_text"],
                    fr["changes"],
                    fr.get("force_entries", []),
                    file_path,
                    file_path,
                    in_place=True,
                )
                if cfg.skip_build_validation:
                    print("Build validation skipped.")
                else:
                    validate_gradle_project_or_rollback(
                        file_path,
                        fr["build_text"],
                        gradle_cmd=get_gradle_cmd(os.path.dirname(os.path.abspath(file_path))),
                        timeout=max(cfg.gradle_timeout, 600),
                        changes=fr.get("changes", []),
                        force_entries=fr.get("force_entries", []),
                        log_dir=log_dir,
                    )
            else:
                print("Nothing to update for this build.gradle.")
        else:
            continue

        file_results.append(fr)

    print("")
    print(
        "Totals: "
        f"{totals['npm_direct']} npm direct, "
        f"{totals['npm_override']} npm override(s), "
        f"{totals['gradle_direct']} Gradle direct, "
        f"{totals['gradle_force']} Gradle force(s), "
        f"{totals['skipped']} skipped"
    )

    report_path = os.path.join(log_dir, "task-completion-report.xlsx")
    generate_task_report(
        ado_tasks=ado_tasks,
        file_results=file_results,
        output_path=report_path,
        auto_open=cfg.auto_open_report,
    )
    print(f"Report: {report_path}")
    print(f"Logs:   {log_dir}")

    return {
        "ado_tasks": ado_tasks,
        "file_results": file_results,
        "report_path": report_path,
        "log_dir": log_dir,
        "totals": totals,
    }


# -- worker -----------------------------------------------------------------
class _Worker(QThread):
    log = pyqtSignal(str)
    done = pyqtSignal(bool, str)
    progress = pyqtSignal(str, int, int)

    def __init__(self, cfg: QuickUpdateConfig) -> None:
        super().__init__()
        self.cfg = cfg

    def run(self) -> None:
        from shared.utils import ProgressBar

        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = Stream(self.log)
        sys.stderr = Stream(self.log)
        ProgressBar._gui_callback = lambda lbl, cur, tot: self.progress.emit(lbl, cur, tot)
        try:
            run_quick_update(self.cfg)
            self.done.emit(True, "Complete")
        except Exception as exc:
            self.log.emit(f"ERROR: {exc}")
            self.log.emit(traceback.format_exc())
            self.done.emit(False, str(exc))
        finally:
            ProgressBar._gui_callback = None
            sys.stdout = old_stdout
            sys.stderr = old_stderr


# -- window -----------------------------------------------------------------
class _Window(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._worker: _Worker | None = None
        self._build()
        self._style()
        self.setWindowTitle("Package Update")
        self.resize(600, 460)

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(8)
        root.setContentsMargins(18, 18, 18, 18)

        root.addWidget(QLabel("Project directory"))
        proj_row = QHBoxLayout()
        self._proj = QLineEdit()
        self._proj.setPlaceholderText("/path/to/project  (scans for package.json and build.gradle)")
        proj_row.addWidget(self._proj)
        browse = QPushButton("Browse")
        browse.setFixedWidth(68)
        browse.clicked.connect(self._browse_proj)
        proj_row.addWidget(browse)
        root.addLayout(proj_row)
        root.addWidget(QLabel("Story URL"))
        self._url = QLineEdit()
        self._url.setPlaceholderText("https://dev.azure.com/org/project/_workitems/edit/12345")
        root.addWidget(self._url)

        self._hint = QLabel("")
        self._hint.setObjectName("hint")
        root.addWidget(self._hint)

        self._run_btn = QPushButton("Run")
        self._run_btn.setFixedHeight(40)
        f = self._run_btn.font()
        f.setBold(True)
        f.setPointSize(f.pointSize() + 1)
        self._run_btn.setFont(f)
        self._run_btn.clicked.connect(self._run)
        root.addWidget(self._run_btn)

        self._prog_label = QLabel("")
        self._prog_label.setObjectName("prog_label")
        self._prog_label.setVisible(False)
        root.addWidget(self._prog_label)

        self._prog = QProgressBar()
        self._prog.setFixedHeight(6)
        self._prog.setTextVisible(False)
        self._prog.setVisible(False)
        root.addWidget(self._prog)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setFont(QFont("Menlo,Consolas,monospace", 11))
        root.addWidget(self._log, stretch=1)

        self._status = QLabel("")
        self._status.setAlignment(Qt.AlignmentFlag.AlignRight)
        root.addWidget(self._status)

    def _browse_proj(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Select project directory")
        if d:
            self._proj.setText(d)
            self._hint.setText("")

    def _run(self) -> None:
        self._hint.setText("")
        proj = self._proj.text().strip()
        url = self._url.text().strip()

        if not proj:
            self._hint.setText("Enter a project directory.")
            return

        from ui.utils import scan_for_dep_managers

        managers = scan_for_dep_managers(proj)
        if not managers:
            self._hint.setText("No package.json or build.gradle found in that directory.")
            return
        self._hint.setText(f"Found {len(managers)} dependency file(s); all will be updated.")

        if not url:
            self._hint.setText("Paste the ADO story URL.")
            return

        parsed = parse_ado_url(url)
        if parsed is None:
            self._hint.setText(
                "Could not parse URL - expected format: "
                "https://dev.azure.com/org/project/_workitems/edit/12345"
            )
            return

        org, project, story_id_str = parsed
        self._log.clear()
        self._status.setText("Running...")
        self._run_btn.setEnabled(False)

        cfg = QuickUpdateConfig(
            project_dir=proj,
            org=org,
            project=project,
            story_id=int(story_id_str),
            auto_open_report=True,
            artifactory_source=os.environ.get("ARTIFACTORY_SOURCE", ""),
            artifactory_repo=os.environ.get("ARTIFACTORY_REPO", "ins-cp-mgmt-gradle-virtual"),
            artifactory_username=os.environ.get("ARTIFACTORY_USERNAME", ""),
            artifactory_password=os.environ.get("ARTIFACTORY_PASSWORD", ""),
        )
        self._worker = _Worker(cfg)
        self._worker.log.connect(self._log.append)
        self._worker.progress.connect(self._on_progress)
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_progress(self, label: str, current: int, total: int) -> None:
        self._prog_label.setText(label)
        self._prog_label.setVisible(True)
        self._prog.setVisible(True)
        if total > 0:
            self._prog.setRange(0, total)
            self._prog.setValue(current)
        else:
            self._prog.setRange(0, 0)

    def _on_done(self, ok: bool, msg: str) -> None:
        self._run_btn.setEnabled(True)
        self._prog.setVisible(False)
        self._prog_label.setVisible(False)
        self._status.setText("Done" if ok else f"Failed: {msg}")

    def _style(self) -> None:
        self.setStyleSheet("""
            QWidget   { background: #1e1e1e; color: #d4d4d4; font-size: 13px; }
            QLabel    { color: #9cdcfe; }
            QLabel#hint      { color: #f48771; font-size: 11px; }
            QLabel#prog_label { color: #888; font-size: 11px; }
            QProgressBar {
                background: #2d2d2d; border: none; border-radius: 3px;
            }
            QProgressBar::chunk { background: #0e639c; border-radius: 3px; }
            QLineEdit {
                background: #2d2d2d; border: 1px solid #3c3c3c;
                border-radius: 3px; padding: 5px 8px; color: #d4d4d4;
            }
            QPushButton {
                background: #0e639c; color: #ffffff; border: none;
                border-radius: 3px; padding: 5px 14px;
            }
            QPushButton:hover    { background: #1177bb; }
            QPushButton:disabled { background: #2d2d2d; color: #666; }
            QTextEdit {
                background: #141414; border: 1px solid #2a2a2a;
                border-radius: 3px; color: #cccccc;
            }
        """)


def _parse_columns(raw: str | None) -> list[str] | None:
    if not raw:
        return None
    return [c.strip() for c in raw.split(",") if c.strip()]


def _add_cli_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--project-dir",
        default=".",
        help="Project root to scan for package.json/build.gradle. Default: current directory",
    )
    parser.add_argument(
        "--package-json",
        action="append",
        default=[],
        help="Explicit package.json file to update. Can be passed multiple times.",
    )
    parser.add_argument(
        "--build-file",
        action="append",
        default=[],
        help="Explicit build.gradle file to update. Can be passed multiple times.",
    )
    parser.add_argument("--story-url", help="Azure DevOps User Story URL")
    parser.add_argument("--org", help="Azure DevOps organization")
    parser.add_argument("--project", help="Azure DevOps project")
    parser.add_argument("--story-id", type=int, help="Azure DevOps User Story ID")
    parser.add_argument("--log-dir", help="Log directory. Default: <project-dir>/logs")
    parser.add_argument(
        "--columns",
        default=None,
        help="CSV columns to scan. Default: title,description,description_html",
    )
    parser.add_argument("--workers", type=int, default=8, help="Parallel workers. Default: 8")
    parser.add_argument("--npm-cmd", default="npm", help="npm command path/name. Default: npm")
    parser.add_argument("--npm-timeout", type=int, default=90, help="npm timeout seconds")
    parser.add_argument("--npm-registry", default=None, help="Optional npm registry URL")
    parser.add_argument("--gradle-timeout", type=int, default=30, help="Gradle timeout seconds")
    parser.add_argument("--skip-block-check", action="store_true", help="Skip block checks")
    parser.add_argument(
        "--skip-build-validation",
        action="store_true",
        help="Do not run npm/Gradle builds after writing updates",
    )
    parser.add_argument("--artifactory-source", default=os.environ.get("ARTIFACTORY_SOURCE", ""))
    parser.add_argument(
        "--artifactory-repo",
        default=os.environ.get("ARTIFACTORY_REPO", "ins-cp-mgmt-gradle-virtual"),
    )
    parser.add_argument(
        "--artifactory-username", default=os.environ.get("ARTIFACTORY_USERNAME", "")
    )
    parser.add_argument(
        "--artifactory-password", default=os.environ.get("ARTIFACTORY_PASSWORD", "")
    )
    parser.add_argument(
        "--open-report",
        action="store_true",
        help="Open the generated Excel report when complete",
    )


def _config_from_args(args: argparse.Namespace) -> QuickUpdateConfig:
    if args.story_url:
        parsed = parse_ado_url(args.story_url)
        if parsed is None:
            raise SystemExit(
                "Could not parse --story-url. Expected "
                "https://dev.azure.com/org/project/_workitems/edit/12345"
            )
        org, project, story_id = parsed
        args.org = args.org or org
        args.project = args.project or project
        args.story_id = args.story_id or int(story_id)
    missing = [name for name in ["org", "project", "story_id"] if getattr(args, name) in (None, "")]
    if missing:
        raise SystemExit(
            "Missing required CLI argument(s): "
            + ", ".join(f"--{name.replace('_', '-')}" for name in missing)
        )

    return QuickUpdateConfig(
        project_dir=args.project_dir,
        org=args.org,
        project=args.project,
        story_id=int(args.story_id),
        log_dir=args.log_dir,
        columns=_parse_columns(args.columns),
        workers=args.workers,
        npm_cmd=args.npm_cmd,
        npm_timeout=args.npm_timeout,
        npm_registry=args.npm_registry,
        gradle_timeout=args.gradle_timeout,
        skip_block_check=args.skip_block_check,
        skip_build_validation=args.skip_build_validation,
        auto_open_report=args.open_report,
        artifactory_source=args.artifactory_source,
        artifactory_repo=args.artifactory_repo,
        artifactory_username=args.artifactory_username,
        artifactory_password=args.artifactory_password,
        package_jsons=args.package_json,
        build_files=args.build_file,
    )


def run_gui() -> None:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = _Window()
    win.show()
    sys.exit(app.exec())


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    parser = argparse.ArgumentParser(description="Quick package update GUI/CLI")
    _add_cli_args(parser)
    parser.add_argument("--gui", action="store_true", help="Launch the GUI explicitly")

    if not argv or argv == ["--gui"]:
        run_gui()
        return

    args = parser.parse_args(argv)
    if args.gui:
        run_gui()
        return
    try:
        run_quick_update(_config_from_args(args))
    except RuntimeError as exc:
        raise SystemExit(f"ERROR: {exc}") from None


if __name__ == "__main__":
    main()
