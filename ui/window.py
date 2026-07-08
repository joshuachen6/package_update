from __future__ import annotations

import contextlib
import os
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from shared.report import skipped_reason_status
from ui.highlighter import TaskHighlighter
from ui.utils import open_url, parse_ado_url, scan_for_dep_managers
from ui.widgets import make_table, mono_textedit
from ui.worker import PipelineWorker

_PARAMS_FILE = Path.home() / ".package_update_gui.json"
_DEFAULT_LOG_DIR = str(Path(__file__).parent.parent / "logs")

_PARAM_LINES = [
    ("_story_url", "story_url", ""),
    ("_org", "org", ""),
    ("_project", "project", ""),
    ("_story", "story_id", ""),
    ("_client_id", "client_id", ""),
    ("_tenant_id", "tenant_id", ""),
    ("_proj_dir", "proj_dir", ""),
    ("_columns_edit", "columns", "title,description,description_html"),
    ("_log_dir", "log_dir", _DEFAULT_LOG_DIR),
    ("_art_src", "artifactory_source", ""),
    ("_art_repo", "artifactory_repo", "ins-cp-mgmt-gradle-virtual"),
    ("_art_user", "artifactory_username", ""),
    ("_npm_registry", "npm_registry", ""),
    ("_npm_cmd", "npm_cmd", "npm"),
]

_PARAM_CHECKS = [
    ("_skip_bc", "skip_block_check", False),
]
_PARAM_SPINS = [
    ("_workers", "workers", 8),
    ("_npm_timeout", "npm_timeout", 90),
    ("_gradle_timeout", "gradle_timeout", 30),
]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Package Update Pipeline")
        self.resize(1440, 860)
        self._worker: PipelineWorker | None = None
        self._results: dict | None = None
        self._dm_items: list = []
        self._setup_ui()
        self._load_params()

    # ── layout ────────────────────────────────────────────────────────────────

    def _setup_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        root_lay = QHBoxLayout(root)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        root_lay.addWidget(splitter)

        splitter.addWidget(self._make_left_panel())
        splitter.addWidget(self._make_right_panel())
        splitter.setSizes([460, 980])

    def _make_left_panel(self) -> QWidget:
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setMinimumWidth(380)
        left_scroll.setMaximumWidth(520)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        left = QWidget()
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(10, 10, 10, 10)
        left_lay.setSpacing(8)

        left_lay.addWidget(self._make_ado_group())
        left_lay.addWidget(self._make_project_group())
        left_lay.addWidget(self._make_options_group())
        left_lay.addWidget(self._make_advanced_group())
        left_lay.addStretch()

        btn_bar = QHBoxLayout()
        self._analyze_btn = QPushButton("▶  Analyze")
        self._write_btn = QPushButton("💾  Write Output")
        self._stop_btn = QPushButton("■  Stop")
        self._clear_btn = QPushButton("Clear Log")
        for b in (self._analyze_btn, self._write_btn, self._stop_btn, self._clear_btn):
            b.setFixedHeight(34)
        self._analyze_btn.setStyleSheet("font-weight: bold; font-size: 13px;")
        self._write_btn.setStyleSheet("font-weight: bold; font-size: 13px; color: #4ec9b0;")
        self._write_btn.setEnabled(False)
        self._stop_btn.setEnabled(False)
        self._analyze_btn.clicked.connect(self._run_analyze)
        self._write_btn.clicked.connect(self._write_output)
        self._stop_btn.clicked.connect(self._stop_pipeline)
        btn_bar.addWidget(self._analyze_btn)
        btn_bar.addWidget(self._write_btn)
        btn_bar.addWidget(self._stop_btn)
        btn_bar.addWidget(self._clear_btn)
        left_lay.addLayout(btn_bar)

        reset_bar = QHBoxLayout()
        self._reset_btn = QPushButton("↺  Reset saved parameters")
        self._reset_btn.setFixedHeight(26)
        self._reset_btn.setStyleSheet("color: #888; font-size: 11px;")
        self._reset_btn.clicked.connect(self._reset_params)
        reset_bar.addStretch()
        reset_bar.addWidget(self._reset_btn)
        left_lay.addLayout(reset_bar)

        left_scroll.setWidget(left)
        return left_scroll

    def _make_right_panel(self) -> QWidget:
        right = QWidget()
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.setSpacing(0)

        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        right_lay.addWidget(self._tabs, stretch=1)

        log_tab = QWidget()
        log_lay = QVBoxLayout(log_tab)
        log_lay.setContentsMargins(0, 0, 0, 0)
        self._log = mono_textedit()
        log_lay.addWidget(self._log)
        self._tabs.addTab(log_tab, "Log")

        self._tabs.addTab(self._make_changes_tab(), "Changes")
        self._tabs.addTab(self._make_tasks_tab(), "ADO Tasks")

        prog_row = QWidget()
        prog_row.setFixedHeight(28)
        prog_lay = QHBoxLayout(prog_row)
        prog_lay.setContentsMargins(8, 2, 8, 2)
        prog_lay.setSpacing(8)
        self._progress_label = QLabel("Idle")
        self._progress_label.setFixedWidth(260)
        self._progress_label.setStyleSheet("color: #888; font-size: 11px;")
        self._progress_bar = QProgressBar()
        self._progress_bar.setFixedHeight(14)
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #555; border-radius: 3px;
                background: #1e1e1e; color: transparent;
            }
            QProgressBar::chunk { background: #264f78; border-radius: 2px; }
        """)
        prog_lay.addWidget(self._progress_label)
        prog_lay.addWidget(self._progress_bar, stretch=1)
        right_lay.addWidget(prog_row)

        self._clear_btn.clicked.connect(self._log.clear)
        return right

    def _make_changes_tab(self) -> QWidget:
        outer = QSplitter(Qt.Orientation.Vertical)

        changes_wrap = QWidget()
        cw_lay = QVBoxLayout(changes_wrap)
        cw_lay.setContentsMargins(4, 4, 4, 0)
        cw_lay.setSpacing(2)

        hdr = QHBoxLayout()
        hdr.addWidget(QLabel("Changes"))
        self._ado_story_btn = QPushButton("Open ADO Story ↗")
        self._ado_story_btn.setFixedHeight(24)
        self._ado_story_btn.setEnabled(False)
        self._ado_story_btn.clicked.connect(self._open_ado_story)
        hdr.addStretch()
        hdr.addWidget(self._ado_story_btn)
        cw_lay.addLayout(hdr)

        self._changes_hint = QLabel("Run Analyze to populate this table.")
        self._changes_hint.setStyleSheet("color: #888; font-style: italic; padding: 4px;")
        cw_lay.addWidget(self._changes_hint)

        self._changes_table = make_table(
            ["File", "Package", "Type", "Old Version", "New Version", "ADO"]
        )
        self._changes_table.setColumnWidth(0, 160)
        self._changes_table.setColumnWidth(1, 200)
        self._changes_table.setColumnWidth(2, 80)
        self._changes_table.setColumnWidth(3, 160)
        self._changes_table.setColumnWidth(4, 160)
        self._changes_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._changes_table.customContextMenuRequested.connect(self._on_changes_context_menu)
        self._changes_table.cellDoubleClicked.connect(
            lambda r, c: self._show_cell_popup(r, c, self._changes_table)
        )
        self._changes_table.selectionModel().currentRowChanged.connect(
            lambda cur, _: self._on_package_row_selected(
                cur.row(), self._changes_table, self._skipped_table
            )
        )
        cw_lay.addWidget(self._changes_table, stretch=1)
        outer.addWidget(changes_wrap)

        skipped_wrap = QWidget()
        sw_lay = QVBoxLayout(skipped_wrap)
        sw_lay.setContentsMargins(4, 0, 4, 0)
        sw_lay.setSpacing(2)
        sw_lay.addWidget(QLabel("Skipped"))

        self._skipped_table = make_table(
            ["File", "Package", "Current Version", "Target Version", "Status", "Reason", "Detail"]
        )
        self._skipped_table.setColumnWidth(0, 160)
        self._skipped_table.setColumnWidth(1, 180)
        self._skipped_table.setColumnWidth(2, 120)
        self._skipped_table.setColumnWidth(3, 120)
        self._skipped_table.setColumnWidth(4, 120)
        self._skipped_table.setColumnWidth(5, 280)
        self._skipped_table.cellDoubleClicked.connect(
            lambda r, c: self._show_cell_popup(r, c, self._skipped_table)
        )
        self._skipped_table.selectionModel().currentRowChanged.connect(
            lambda cur, _: self._on_package_row_selected(
                cur.row(), self._skipped_table, self._changes_table
            )
        )
        sw_lay.addWidget(self._skipped_table, stretch=1)
        outer.addWidget(skipped_wrap)

        related_wrap = QWidget()
        rw_lay = QVBoxLayout(related_wrap)
        rw_lay.setContentsMargins(4, 0, 4, 4)
        rw_lay.setSpacing(2)

        self._related_header = QLabel("Tasks mentioning: —")
        self._related_header.setStyleSheet("color: #888; font-style: italic; padding: 2px;")
        rw_lay.addWidget(self._related_header)

        inner = QSplitter(Qt.Orientation.Horizontal)

        self._related_list = QListWidget()
        self._related_list.setStyleSheet(
            "QListWidget { background: #1e1e1e; border: none; }"
            "QListWidget::item { padding: 4px 8px; color: #d4d4d4; }"
            "QListWidget::item:selected { background: #264f78; }"
        )
        self._related_list.currentItemChanged.connect(self._on_related_task_selected)
        self._related_list.itemDoubleClicked.connect(
            lambda item: open_url(item.data(Qt.ItemDataRole.UserRole).get("url", ""))
        )
        inner.addWidget(self._related_list)

        self._related_detail = mono_textedit(
            "Select a task from the list to see its description.\n"
            "Double-click to open in Azure DevOps."
        )
        self._related_highlighter = TaskHighlighter(self._related_detail.document())
        inner.addWidget(self._related_detail)
        inner.setSizes([280, 560])

        rw_lay.addWidget(inner, stretch=1)
        outer.addWidget(related_wrap)

        outer.setSizes([300, 160, 260])

        wrapper = QWidget()
        wl = QVBoxLayout(wrapper)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.addWidget(outer)
        return wrapper

    def _make_tasks_tab(self) -> QWidget:
        splitter = QSplitter(Qt.Orientation.Vertical)

        self._task_list = QListWidget()
        self._task_list.setStyleSheet(
            "QListWidget { background: #1e1e1e; border: none; }"
            "QListWidget::item { padding: 5px 8px; color: #d4d4d4; }"
            "QListWidget::item:selected { background: #264f78; }"
        )
        self._task_list.currentItemChanged.connect(self._on_task_selected)
        self._task_list.itemDoubleClicked.connect(self._on_task_double_clicked)
        splitter.addWidget(self._task_list)

        self._task_detail = mono_textedit(
            "Select a task to see its description.\n"
            "Double-click a task to open it in Azure DevOps.\n\n"
            "Package names are highlighted in blue.\n"
            "Version numbers are highlighted in teal."
        )
        self._task_highlighter = TaskHighlighter(self._task_detail.document())
        splitter.addWidget(self._task_detail)
        splitter.setSizes([220, 460])

        wrapper = QWidget()
        wl = QVBoxLayout(wrapper)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.addWidget(splitter)
        return wrapper

    # ── group builders ────────────────────────────────────────────────────────

    def _make_ado_group(self) -> QGroupBox:
        g = QGroupBox("ADO Connection")
        lay = QFormLayout(g)
        lay.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        lay.setSpacing(6)

        auth_w = QWidget()
        auth_l = QHBoxLayout(auth_w)
        auth_l.setContentsMargins(0, 0, 0, 0)
        self._rb_azcli = QRadioButton("Azure CLI  (az login)")
        self._rb_msal = QRadioButton("MSAL  (browser)")
        self._rb_azcli.setChecked(True)
        auth_l.addWidget(self._rb_azcli)
        auth_l.addWidget(self._rb_msal)
        auth_l.addStretch()
        lay.addRow("Auth:", auth_w)

        self._story_url = QLineEdit()
        self._story_url.setPlaceholderText(
            "https://dev.azure.com/org/project/_workitems/edit/12345  (auto-fills fields below)"
        )
        self._story_url.textChanged.connect(self._on_story_url_changed)
        lay.addRow("Story URL:", self._story_url)

        self._org = QLineEdit()
        self._org.setPlaceholderText("my-org")
        self._project = QLineEdit()
        self._project.setPlaceholderText("MyProject")
        self._story = QLineEdit()
        self._story.setPlaceholderText("12345")
        lay.addRow("Org:", self._org)
        lay.addRow("Project:", self._project)
        lay.addRow("Story ID:", self._story)

        self._msal_box = QWidget()
        msal_lay = QFormLayout(self._msal_box)
        msal_lay.setContentsMargins(0, 0, 0, 0)
        msal_lay.setSpacing(6)
        self._client_id = QLineEdit()
        self._client_id.setPlaceholderText("xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx")
        self._tenant_id = QLineEdit()
        self._tenant_id.setPlaceholderText("(optional)")
        msal_lay.addRow("Client ID:", self._client_id)
        msal_lay.addRow("Tenant ID:", self._tenant_id)
        lay.addRow(self._msal_box)

        self._msal_box.setVisible(False)
        self._rb_msal.toggled.connect(self._msal_box.setVisible)
        return g

    def _make_project_group(self) -> QGroupBox:
        g = QGroupBox("Project Directory & Dependency Files")
        lay = QVBoxLayout(g)
        lay.setSpacing(6)

        dir_row = QHBoxLayout()
        self._proj_dir = QLineEdit()
        self._proj_dir.setPlaceholderText("Select project root directory…")
        browse = QPushButton("Browse…")
        browse.setFixedWidth(80)
        browse.clicked.connect(self._browse_dir)
        dir_row.addWidget(self._proj_dir)
        dir_row.addWidget(browse)
        lay.addLayout(dir_row)

        scan_btn = QPushButton("Scan for Dependency Files")
        scan_btn.clicked.connect(self._scan_project)
        lay.addWidget(scan_btn)

        self._dm_container = QWidget()
        self._dm_layout = QVBoxLayout(self._dm_container)
        self._dm_layout.setContentsMargins(4, 4, 4, 4)
        self._dm_layout.setSpacing(3)

        self._dm_hint = QLabel("(press Scan to detect dependency files)")
        self._dm_hint.setStyleSheet("color: #888; font-style: italic; padding: 2px;")
        self._dm_layout.addWidget(self._dm_hint)

        dm_scroll = QScrollArea()
        dm_scroll.setWidget(self._dm_container)
        dm_scroll.setWidgetResizable(True)
        dm_scroll.setFixedHeight(130)
        dm_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        lay.addWidget(dm_scroll)
        return g

    def _make_options_group(self) -> QGroupBox:
        g = QGroupBox("Options")
        lay = QFormLayout(g)
        lay.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        lay.setSpacing(6)

        flags = QWidget()
        fl = QHBoxLayout(flags)
        fl.setContentsMargins(0, 0, 0, 0)
        self._skip_bc = QCheckBox("Skip Block Check")
        fl.addWidget(self._skip_bc)
        fl.addStretch()
        lay.addRow("Flags:", flags)

        self._workers = QSpinBox()
        self._workers.setRange(1, 32)
        self._workers.setValue(8)
        lay.addRow("Workers:", self._workers)

        self._columns_edit = QLineEdit("title,description,description_html")
        lay.addRow("CSV Columns:", self._columns_edit)

        self._log_dir = QLineEdit(_DEFAULT_LOG_DIR)
        lay.addRow("Log Dir:", self._log_dir)
        return g

    def _make_advanced_group(self) -> QGroupBox:
        g = QGroupBox("Advanced  (Artifactory / npm)")
        g.setCheckable(True)
        g.setChecked(False)
        lay = QFormLayout(g)
        lay.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        lay.setSpacing(6)

        def _env(key, default=""):
            return os.environ.get(key, default)

        self._art_src = QLineEdit(_env("ARTIFACTORY_SOURCE"))
        self._art_src.setPlaceholderText("https://company.jfrog.io/artifactory")
        self._art_repo = QLineEdit(_env("ARTIFACTORY_REPO", "ins-cp-mgmt-gradle-virtual"))
        self._art_user = QLineEdit(_env("ARTIFACTORY_USERNAME"))
        self._art_pass = QLineEdit(_env("ARTIFACTORY_PASSWORD"))
        self._art_pass.setEchoMode(QLineEdit.EchoMode.Password)
        lay.addRow("Artifactory URL:", self._art_src)
        lay.addRow("Artifactory Repo:", self._art_repo)
        lay.addRow("Artifactory User:", self._art_user)
        lay.addRow("Artifactory Pass:", self._art_pass)

        self._npm_registry = QLineEdit()
        self._npm_registry.setPlaceholderText("(blank = use .npmrc)")
        self._npm_cmd = QLineEdit("npm")
        lay.addRow("npm Registry:", self._npm_registry)
        lay.addRow("npm Command:", self._npm_cmd)

        self._npm_timeout = QSpinBox()
        self._npm_timeout.setRange(10, 600)
        self._npm_timeout.setValue(90)
        self._npm_timeout.setSuffix(" s")
        lay.addRow("npm Timeout:", self._npm_timeout)

        self._gradle_timeout = QSpinBox()
        self._gradle_timeout.setRange(5, 300)
        self._gradle_timeout.setValue(30)
        self._gradle_timeout.setSuffix(" s")
        lay.addRow("Gradle Timeout:", self._gradle_timeout)
        return g

    # ── interactions ──────────────────────────────────────────────────────────

    def _on_story_url_changed(self, text: str):
        parsed = parse_ado_url(text)
        if parsed is None:
            return
        org, project, story_id = parsed
        self._org.setText(org)
        self._project.setText(project)
        self._story.setText(story_id)

    def _browse_dir(self):
        start = self._proj_dir.text().strip() or str(Path.home())
        d = QFileDialog.getExistingDirectory(self, "Select Project Directory", start)
        if d:
            self._proj_dir.setText(d)

    def _scan_project(self):
        proj = self._proj_dir.text().strip()
        if not proj or not os.path.isdir(proj):
            self._log_warn("Set a valid project directory first.")
            return

        for cb, _ in self._dm_items:
            cb.deleteLater()
        self._dm_items.clear()
        if self._dm_hint is not None:
            self._dm_hint.deleteLater()
            self._dm_hint = None

        managers = scan_for_dep_managers(proj)
        if not managers:
            self._dm_hint = QLabel("(no package.json / build.gradle found)")
            self._dm_hint.setStyleSheet("color: #888; font-style: italic; padding: 2px;")
            self._dm_layout.addWidget(self._dm_hint)
            self._log_info("Scan complete — no dependency files found.")
            return

        for dm in managers:
            cb = QCheckBox(dm["label"])
            cb.setChecked(True)
            self._dm_layout.addWidget(cb)
            self._dm_items.append((cb, dm))

        self._log_info(f"Scan complete — {len(managers)} dependency file(s) found.")

    def _build_config(self) -> dict | None:
        def _req(w, name: str) -> str | None:
            v = w.text().strip()
            if not v:
                self._log_err(f"'{name}' is required.")
            return v or None

        org = _req(self._org, "Org")
        if not org:
            return None
        project = _req(self._project, "Project")
        if not project:
            return None
        story_id = _req(self._story, "Story ID")
        if not story_id:
            return None
        if not story_id.isdigit():
            self._log_err("Story ID must be a number.")
            return None

        auth = "azcli" if self._rb_azcli.isChecked() else "msal"
        client_id = tenant_id = ""
        if auth == "msal":
            client_id = _req(self._client_id, "Client ID")
            if not client_id:
                return None
            tenant_id = self._tenant_id.text().strip()

        proj_dir = self._proj_dir.text().strip()
        if proj_dir and not os.path.isdir(proj_dir):
            self._log_err("Project directory does not exist.")
            return None

        selected = [(cb, dm) for cb, dm in self._dm_items if cb.isChecked()]
        if not selected:
            self._log_err("No dependency files selected — run Scan and check at least one.")
            return None

        log_dir_raw = self._log_dir.text().strip() or _DEFAULT_LOG_DIR
        if os.path.isabs(log_dir_raw):
            log_dir = log_dir_raw
        else:
            log_dir = str(Path(__file__).parent.parent / log_dir_raw)

        return {
            "org": org,
            "project": project,
            "story_id": story_id,
            "auth_method": auth,
            "client_id": client_id,
            "tenant_id": tenant_id,
            "dep_managers": [dm for _, dm in selected],
            "proj_dir": proj_dir or ".",
            "skip_block_check": self._skip_bc.isChecked(),
            "workers": self._workers.value(),
            "columns": self._columns_edit.text().strip(),
            "log_dir": log_dir,
            "artifactory_source": self._art_src.text().strip(),
            "artifactory_repo": self._art_repo.text().strip(),
            "artifactory_username": self._art_user.text().strip(),
            "artifactory_password": self._art_pass.text(),
            "npm_registry": self._npm_registry.text().strip() or None,
            "npm_cmd": self._npm_cmd.text().strip() or "npm",
            "npm_timeout": self._npm_timeout.value(),
            "gradle_timeout": self._gradle_timeout.value(),
        }

    def _run_analyze(self):
        if self._worker and self._worker.isRunning():
            return
        cfg = self._build_config()
        if cfg is None:
            return

        self._save_params()
        self._results = None
        self._write_btn.setEnabled(False)
        self._ado_story_btn.setEnabled(False)
        self._analyze_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._progress_bar.setRange(0, 0)
        self._progress_label.setText("Starting…")
        self._tabs.setCurrentIndex(0)
        self._log_info("Analysis started.")

        self._worker = PipelineWorker(cfg)
        self._worker.log_line.connect(self._append)
        self._worker.err_line.connect(self._append_err)
        self._worker.step_done.connect(self._on_step_done)
        self._worker.progress.connect(self._on_progress)
        self._worker.results_ready.connect(self._on_results_ready)
        self._worker.all_done.connect(self._on_all_done)
        self._worker.start()

    def _write_output(self):
        if not self._results:
            self._log_warn("No analysis results — run Analyze first.")
            return

        from output.gradle import write_gradle_file
        from output.node import write_package_json
        from parsers.gradle_tree import get_gradle_cmd
        from shared.build_validation import (
            validate_gradle_project_or_rollback,
            validate_node_project_or_rollback,
        )

        any_written = False
        for fr in self._results.get("file_results", []):
            dm_type = fr["dm_type"]
            fpath = fr["file_path"]
            try:
                if dm_type == "node":
                    pkg_json_path = fr["pkg_json_path"]
                    original_text = Path(pkg_json_path).read_text(encoding="utf-8")
                    write_package_json(fr["pkg"], pkg_json_path, pkg_json_path, in_place=True)
                    validate_node_project_or_rollback(
                        pkg_json_path,
                        original_text,
                        npm_cmd=self._results.get("cfg", {}).get("npm_cmd", "npm"),
                        timeout=max(self._results.get("cfg", {}).get("npm_timeout", 90), 600),
                        direct_changes=fr.get("direct_changes", []),
                        override_changes=fr.get("override_changes", []),
                        log_dir=self._results.get("cfg", {}).get("log_dir"),
                    )
                    self._log_info(f"Node written and build-validated → {pkg_json_path}")
                    any_written = True
                elif dm_type == "gradle":
                    build_file = fr["build_file"]
                    write_gradle_file(
                        fr["build_text"],
                        fr["changes"],
                        fr.get("force_entries", []),
                        build_file,
                        build_file,
                        in_place=True,
                    )
                    validate_gradle_project_or_rollback(
                        build_file,
                        fr["build_text"],
                        gradle_cmd=get_gradle_cmd(os.path.dirname(os.path.abspath(build_file))),
                        timeout=max(self._results.get("cfg", {}).get("gradle_timeout", 30), 600),
                        changes=fr.get("changes", []),
                        force_entries=fr.get("force_entries", []),
                        log_dir=self._results.get("cfg", {}).get("log_dir"),
                    )
                    self._log_info(f"Gradle written and build-validated → {build_file}")
                    any_written = True
            except Exception as exc:
                self._log_err(f"Write failed for {fpath}: {exc}")

        if any_written:
            self._log_info("All files written.")
        else:
            self._log_warn("Nothing to write.")

    def _stop_pipeline(self):
        if self._worker:
            self._worker.abort()
        self._log_warn("Stop requested — will halt after current step.")

    def _open_ado_story(self):
        if self._results and self._results.get("story_url"):
            open_url(self._results["story_url"])

    # ── parameter persistence ─────────────────────────────────────────────────

    def _load_params(self):
        import json

        try:
            data = json.loads(_PARAMS_FILE.read_text())
        except Exception:
            return
        for attr, key, _ in _PARAM_LINES:
            if key in data:
                getattr(self, attr).setText(str(data[key]))
        for attr, key, _ in _PARAM_CHECKS:
            if key in data:
                getattr(self, attr).setChecked(bool(data[key]))
        for attr, key, _ in _PARAM_SPINS:
            if key in data:
                with contextlib.suppress(TypeError, ValueError):
                    getattr(self, attr).setValue(int(data[key]))
        if data.get("auth_method") == "msal":
            self._rb_msal.setChecked(True)
        else:
            self._rb_azcli.setChecked(True)

    def _save_params(self):
        import json

        data: dict = {}
        for attr, key, _ in _PARAM_LINES:
            data[key] = getattr(self, attr).text().strip()
        for attr, key, _ in _PARAM_CHECKS:
            data[key] = getattr(self, attr).isChecked()
        for attr, key, _ in _PARAM_SPINS:
            data[key] = getattr(self, attr).value()
        data["auth_method"] = "msal" if self._rb_msal.isChecked() else "azcli"
        with contextlib.suppress(Exception):
            _PARAMS_FILE.write_text(json.dumps(data, indent=2))

    def _reset_params(self):
        with contextlib.suppress(Exception):
            _PARAMS_FILE.unlink(missing_ok=True)
        for attr, _key, default in _PARAM_LINES:
            getattr(self, attr).setText(default)
        for attr, _key, default in _PARAM_CHECKS:
            getattr(self, attr).setChecked(default)
        for attr, _key, default in _PARAM_SPINS:
            getattr(self, attr).setValue(default)
        self._rb_azcli.setChecked(True)
        self._log_info("Parameters reset to defaults.")

    # ── signal handlers ───────────────────────────────────────────────────────

    def _on_step_done(self, step: str, ok: bool):
        if ok:
            self._append_colored(f"✓  Step '{step}' completed.", "#4ec9b0")
        else:
            self._append_err(f"✗  Step '{step}' failed.")

    def _on_progress(self, label: str, current: int, total: int):
        self._progress_label.setText(label)
        if total > 0:
            self._progress_bar.setRange(0, total)
            self._progress_bar.setValue(current)
        else:
            self._progress_bar.setRange(0, 0)

    def _on_results_ready(self, results: dict):
        self._results = results
        self._write_btn.setEnabled(True)
        self._ado_story_btn.setEnabled(True)
        self._populate_changes_table(results)
        self._populate_skipped_table(results)
        self._populate_tasks_tab(results.get("ado_tasks", []))

        all_pkgs: set = set()
        for fr in results.get("file_results", []):
            for ch in fr.get("display_changes", []):
                all_pkgs.add(ch["package"])
            for sk in fr.get("skipped_display", []):
                if sk.get("package"):
                    all_pkgs.add(sk["package"])
        self._task_highlighter.set_packages(all_pkgs)
        self._related_highlighter.set_packages(all_pkgs)

        total_changes = sum(
            len(fr.get("display_changes", [])) for fr in results.get("file_results", [])
        )
        total_skipped = sum(
            len(fr.get("skipped_display", [])) for fr in results.get("file_results", [])
        )
        self._append_colored(
            f"✓  Analysis complete — {total_changes} change(s), {total_skipped} skipped. "
            "See Changes and ADO Tasks tabs.",
            "#4ec9b0",
        )
        self._tabs.setCurrentIndex(1)

        ado_tasks = results.get("ado_tasks", [])
        if ado_tasks:
            self._generate_report(results)

    def _generate_report(self, results: dict) -> None:
        from shared.report import generate_task_report

        log_dir_raw = self._log_dir.text().strip() or _DEFAULT_LOG_DIR
        log_dir = (
            log_dir_raw
            if os.path.isabs(log_dir_raw)
            else str(Path(__file__).parent.parent / log_dir_raw)
        )
        report_path = os.path.join(log_dir, "task-completion-report.xlsx")
        try:
            generate_task_report(
                ado_tasks=results.get("ado_tasks", []),
                file_results=results.get("file_results", []),
                output_path=report_path,
                auto_open=True,
            )
            self._append_colored(f"  Report: {report_path}", "#9cdcfe")
        except Exception as exc:
            self._append_colored(f"  Report generation failed: {exc}", "#f44747")

    def _on_all_done(self):
        self._analyze_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(100)
        self._progress_label.setText("Done")

    # ── context menu ──────────────────────────────────────────────────────────

    def _on_changes_context_menu(self, pos):
        if not self._results:
            return
        menu = QMenu(self)
        story_url = self._results.get("story_url", "")
        if story_url:
            act = menu.addAction("Open ADO Story ↗")
            act.triggered.connect(lambda: open_url(story_url))
        menu.exec(self._changes_table.viewport().mapToGlobal(pos))

    def _show_cell_popup(self, row: int, col: int, table: QTableWidget) -> None:
        item = table.item(row, col)
        if not item or not item.text():
            return
        header = table.horizontalHeaderItem(col)
        title = header.text() if header else "Cell Value"
        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        dlg.setMinimumSize(500, 200)
        lay = QVBoxLayout(dlg)
        te = QTextEdit()
        te.setReadOnly(True)
        te.setPlainText(item.text())
        te.setFont(QFont("Courier New", 10))
        lay.addWidget(te)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bb.rejected.connect(dlg.reject)
        lay.addWidget(bb)
        dlg.exec()

    # ── row selection → related tasks pane ───────────────────────────────────

    def _on_package_row_selected(self, row: int, table: QTableWidget, other: QTableWidget):
        if row < 0:
            return
        item = table.item(row, 0)
        if item is None:
            return
        d = item.data(Qt.ItemDataRole.UserRole)
        if not d:
            return
        other.blockSignals(True)
        other.clearSelection()
        other.blockSignals(False)
        pkg = d.get("package", "")
        task_ids = d.get("task_ids", [])
        self._show_related_tasks(pkg, task_ids)

    def _show_related_tasks(self, package_name: str, task_ids: list):
        self._related_list.clear()
        self._related_detail.clear()
        self._related_highlighter.set_packages({package_name} if package_name else set())

        task_map = {t["id"]: t for t in (self._results or {}).get("ado_tasks", [])}
        matches = [task_map[tid] for tid in task_ids if tid in task_map]

        if matches:
            self._related_header.setText(
                f"Tasks mentioning '{package_name}'  ({len(matches)} found)"
            )
            for task in matches:
                label = f"[{task['id']}]  {task['title']}"
                if task.get("state"):
                    label += f"  ({task['state']})"
                list_item = QListWidgetItem(label)
                list_item.setData(Qt.ItemDataRole.UserRole, task)
                self._related_list.addItem(list_item)
            self._related_list.setCurrentRow(0)
        else:
            self._related_header.setText(f"No ADO task data for '{package_name}'")

    def _on_related_task_selected(self, current: QListWidgetItem | None, _prev):
        if current is None:
            return
        task = current.data(Qt.ItemDataRole.UserRole)
        lines = [
            f"[{task['id']}] {task['title']}",
            f"State:       {task.get('state', '')}",
        ]
        if task.get("assigned_to"):
            lines.append(f"Assigned To: {task['assigned_to']}")
        lines.append(f"URL:         {task.get('url', '')}")
        lines.append("")
        lines.append("─" * 70)
        lines.append("")
        lines.append(task.get("description") or "(No description)")
        self._related_detail.setPlainText("\n".join(lines))

    # ── table / task population ───────────────────────────────────────────────

    def _populate_changes_table(self, results: dict):
        self._changes_hint.hide()
        self._changes_table.setRowCount(0)
        proj_dir = results.get("cfg", {}).get("proj_dir", ".")

        type_colors = {
            "direct": "#569cd6",
            "override": "#dcdcaa",
            "gradle": "#ce9178",
            "block-fix": "#c586c0",
        }

        for fr in results.get("file_results", []):
            try:
                file_label = os.path.relpath(fr["file_path"], proj_dir)
            except ValueError:
                file_label = fr["file_path"]

            for ch in fr.get("display_changes", []):
                row = self._changes_table.rowCount()
                self._changes_table.insertRow(row)

                file_item = QTableWidgetItem(file_label)
                file_item.setForeground(QColor("#888"))
                file_item.setData(Qt.ItemDataRole.UserRole, {**ch, "file": file_label})
                self._changes_table.setItem(row, 0, file_item)

                self._changes_table.setItem(row, 1, QTableWidgetItem(ch["package"]))

                ctype = ch["change_type"]
                type_item = QTableWidgetItem(ctype)
                type_item.setForeground(QColor(type_colors.get(ctype, "#d4d4d4")))
                self._changes_table.setItem(row, 2, type_item)

                old_item = QTableWidgetItem(ch["old"])
                old_item.setForeground(QColor("#f44747"))
                self._changes_table.setItem(row, 3, old_item)

                new_item = QTableWidgetItem(ch["new"])
                new_item.setForeground(QColor("#4ec9b0"))
                self._changes_table.setItem(row, 4, new_item)

                ado_item = QTableWidgetItem("✓" if ch["ado_guided"] else "")
                if ch["ado_guided"]:
                    ado_item.setForeground(QColor("#4ec9b0"))
                    ado_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self._changes_table.setItem(row, 5, ado_item)

    def _populate_skipped_table(self, results: dict):
        self._skipped_table.setRowCount(0)
        proj_dir = results.get("cfg", {}).get("proj_dir", ".")

        for fr in results.get("file_results", []):
            try:
                file_label = os.path.relpath(fr["file_path"], proj_dir)
            except ValueError:
                file_label = fr["file_path"]

            for r in fr.get("skipped_display", []):
                row = self._skipped_table.rowCount()
                self._skipped_table.insertRow(row)

                file_item = QTableWidgetItem(file_label)
                file_item.setForeground(QColor("#888"))
                file_item.setData(Qt.ItemDataRole.UserRole, {**r, "file": file_label})
                self._skipped_table.setItem(row, 0, file_item)

                self._skipped_table.setItem(row, 1, QTableWidgetItem(r.get("package", "")))

                cur_item = QTableWidgetItem(r.get("current", ""))
                cur_item.setForeground(QColor("#888"))
                self._skipped_table.setItem(row, 2, cur_item)

                tgt_item = QTableWidgetItem(r.get("target", ""))
                tgt_item.setForeground(QColor("#dcdcaa"))
                self._skipped_table.setItem(row, 3, tgt_item)

                status = skipped_reason_status(r.get("reason", ""))
                status_item = QTableWidgetItem(status)
                if status == "Could not update":
                    status_item.setForeground(QColor("#f44747"))
                    status_item.setFont(QFont("", -1, QFont.Weight.Bold))
                elif status == "Resolved":
                    status_item.setForeground(QColor("#4ec9b0"))
                else:
                    status_item.setForeground(QColor("#dcdcaa"))
                self._skipped_table.setItem(row, 4, status_item)

                self._skipped_table.setItem(row, 5, QTableWidgetItem(r.get("reason", "")))

                detail_item = QTableWidgetItem(r.get("detail", ""))
                detail_item.setForeground(QColor("#888"))
                self._skipped_table.setItem(row, 6, detail_item)

    def _populate_tasks_tab(self, tasks: list):
        self._task_list.clear()
        self._task_detail.clear()
        for task in tasks:
            label = f"[{task['id']}]  {task['title']}"
            if task.get("state"):
                label += f"  ({task['state']})"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, task)
            self._task_list.addItem(item)

    def _on_task_selected(self, current: QListWidgetItem | None, _previous):
        if current is None:
            return
        task = current.data(Qt.ItemDataRole.UserRole)
        lines = [
            f"[{task['id']}] {task['title']}",
            f"State:       {task.get('state', '')}",
        ]
        if task.get("assigned_to"):
            lines.append(f"Assigned To: {task['assigned_to']}")
        lines.append(f"URL:         {task.get('url', '')}")
        lines.append("")
        lines.append("─" * 70)
        lines.append("")
        lines.append(task.get("description") or "(No description)")
        self._task_detail.setPlainText("\n".join(lines))

    def _on_task_double_clicked(self, item: QListWidgetItem):
        task = item.data(Qt.ItemDataRole.UserRole)
        url = task.get("url", "")
        if url:
            open_url(url)

    # ── log helpers ───────────────────────────────────────────────────────────

    def _append_colored(self, text: str, color: str):
        c = self._log.textCursor()
        c.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        c.setCharFormat(fmt)
        c.insertText(text + "\n")
        self._log.setTextCursor(c)
        self._log.ensureCursorVisible()

    def _append(self, text: str):
        self._append_colored(text, "#d4d4d4")

    def _append_err(self, text: str):
        self._append_colored(text, "#f44747")

    def _log_info(self, text: str):
        self._append_colored(f"[info]  {text}", "#569cd6")

    def _log_warn(self, text: str):
        self._append_colored(f"[warn]  {text}", "#dcdcaa")

    def _log_err(self, text: str):
        self._append_colored(f"[error] {text}", "#f44747")
