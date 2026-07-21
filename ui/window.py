from __future__ import annotations

import contextlib
import os
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
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

from shared.report import generate_report, skipped_reason_status
from shared.utils import normalize_log_dir
from ui.batch_tab import BatchTab
from ui.highlighter import TaskHighlighter
from ui.utils import open_url
from ui.widgets import make_table, mono_textedit
from ui.worker import PipelineWorker
from ui.write_worker import WriteOutputWorker

_PARAMS_FILE = Path.home() / ".package_update_gui.json"
_DEFAULT_LOG_DIR = str(Path(__file__).parent.parent / "logs")

_PARAM_LINES = [
    ("_github_url", "github_url", ""),
    ("_checkout_dir", "checkout_dir", str(Path.home() / ".package_update_gui" / "repos")),
    ("_branch_combo", "branch", ""),
    ("_columns_edit", "columns", ""),
    ("_log_dir", "log_dir", _DEFAULT_LOG_DIR),
    ("_art_src", "artifactory_source", ""),
    ("_art_repo", "artifactory_repo", "ins-cp-mgmt-gradle-virtual"),
    ("_art_user", "artifactory_username", ""),
    ("_xray_url", "xray_url", ""),
    ("_npm_registry", "npm_registry", ""),
    ("_npm_cmd", "npm_cmd", "npm"),
]
_PARAM_CHECKS = [
    ("_skip_bc", "skip_block_check", False),
    ("_capture_build_logs", "capture_build_logs", False),
]
_PARAM_SPINS = [
    ("_workers", "workers", 8),
    ("_npm_timeout", "npm_timeout", 90),
    ("_gradle_timeout", "gradle_timeout", 150),
]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Package Update Pipeline")
        self.resize(1440, 860)
        self._worker: PipelineWorker | None = None
        self._write_worker: WriteOutputWorker | None = None
        self._results: dict | None = None
        self._branch_url: str = ""
        self._pending_log_lines: list[tuple[str, str]] = []
        self._log_flush_timer = QTimer(self)
        self._log_flush_timer.setInterval(50)
        self._log_flush_timer.timeout.connect(
            self._flush_pending_log_lines
        )
        self._log_flush_timer.start()
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

        left_lay.addWidget(self._make_github_group())
        left_lay.addWidget(self._make_options_group())
        left_lay.addWidget(self._make_advanced_group())
        left_lay.addStretch()

        btn_wrap = QVBoxLayout()
        btn_row1 = QHBoxLayout()
        btn_row2 = QHBoxLayout()

        self._analyze_btn = QPushButton("▶  Analyze")
        self._write_btn = QPushButton("💾  Write Output")
        self._phase2_btn = QPushButton("⚠  Run Phase 2 Isolation")
        self._stop_btn = QPushButton("■  Stop")
        self._clear_btn = QPushButton("Clear Log")

        for b in (self._analyze_btn, self._write_btn, self._phase2_btn, self._stop_btn, self._clear_btn):
            b.setFixedHeight(34)

        self._analyze_btn.setStyleSheet("font-weight: bold; font-size: 13px;")
        self._write_btn.setStyleSheet("font-weight: bold; font-size: 13px; color: #4ec9b0;")

        self._write_btn.setEnabled(False)
        self._phase2_btn.setEnabled(False)
        self._stop_btn.setEnabled(False)

        self._analyze_btn.clicked.connect(self._run_analyze)
        self._write_btn.clicked.connect(self._write_output)
        self._phase2_btn.clicked.connect(self._run_phase2)
        self._stop_btn.clicked.connect(self._stop_pipeline)

        btn_row1.addWidget(self._analyze_btn)
        btn_row1.addWidget(self._write_btn)
        btn_row1.addWidget(self._phase2_btn)

        btn_row2.addWidget(self._stop_btn)
        btn_row2.addWidget(self._clear_btn)

        btn_wrap.addLayout(btn_row1)
        btn_wrap.addLayout(btn_row2)

        left_lay.addLayout(btn_wrap)

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
        self._tabs.addTab(self._make_cves_tab(), "CVEs")
        self._batch_tab = BatchTab(get_settings=self._build_shared_settings)
        self._tabs.addTab(self._batch_tab, "Batch")

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
        self._github_repo_btn = QPushButton("Open GitHub Repo ↗")
        self._github_repo_btn.setFixedHeight(24)
        self._github_repo_btn.setEnabled(False)
        self._github_repo_btn.clicked.connect(self._open_github_repo)
        hdr.addStretch()
        hdr.addWidget(self._github_repo_btn)
        cw_lay.addLayout(hdr)

        self._changes_hint = QLabel("Run Analyze to populate this table.")
        self._changes_hint.setStyleSheet("color: #888; font-style: italic; padding: 4px;")
        cw_lay.addWidget(self._changes_hint)

        self._changes_table = make_table(
            ["File", "Package", "Type", "Old Version", "New Version", "Source"]
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

        self._related_header = QLabel("Package context: —")
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
            "JFrog audit results and related package context appear in the log."
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

    def _make_cves_tab(self) -> QWidget:
        wrapper = QWidget()
        lay = QVBoxLayout(wrapper)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(2)

        hdr = QHBoxLayout()
        hdr.addWidget(QLabel("CVEs found by JFrog audit"))
        hdr.addStretch()
        lay.addLayout(hdr)

        self._cves_hint = QLabel("Run Analyze to populate CVEs found by JFrog audit.")
        self._cves_hint.setStyleSheet("color: #888; font-style: italic; padding: 4px;")
        lay.addWidget(self._cves_hint)

        self._cves_table = make_table(["Ecosystem", "Package", "Version", "CVEs", "Component"])
        self._cves_table.setColumnWidth(0, 100)
        self._cves_table.setColumnWidth(1, 240)
        self._cves_table.setColumnWidth(2, 120)
        self._cves_table.setColumnWidth(3, 240)
        self._cves_table.setColumnWidth(4, 360)
        self._cves_table.cellDoubleClicked.connect(
            lambda r, c: self._show_cell_popup(r, c, self._cves_table)
        )
        lay.addWidget(self._cves_table, stretch=1)

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
            "Double-click a result to view details.\n\n"
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

    def _make_github_group(self) -> QGroupBox:
        g = QGroupBox("GitHub Repository")
        lay = QFormLayout(g)
        lay.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        lay.setSpacing(6)
        self._github_url = QLineEdit()
        self._github_url.setPlaceholderText("https://github.com/org/repo.git")
        self._github_url.textChanged.connect(self._on_github_url_changed)
        lay.addRow("Repo URL:", self._github_url)
        self._checkout_dir = QLineEdit(str(Path.home() / ".package_update_gui" / "repos"))
        self._checkout_dir.setPlaceholderText("Local checkout parent directory")
        lay.addRow("Clone To:", self._checkout_dir)
        branch_row = QWidget()
        branch_lay = QHBoxLayout(branch_row)
        branch_lay.setContentsMargins(0, 0, 0, 0)
        branch_lay.setSpacing(6)
        self._branch_combo = QComboBox()
        self._branch_combo.setEditable(True)
        self._branch_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._branch_combo.lineEdit().setPlaceholderText("(default branch)")
        self._fetch_branches_btn = QPushButton("Fetch Branches")
        self._fetch_branches_btn.setFixedHeight(28)
        self._fetch_branches_btn.clicked.connect(self._fetch_branches)
        branch_lay.addWidget(self._branch_combo, stretch=1)
        branch_lay.addWidget(self._fetch_branches_btn)
        lay.addRow("Branch:", branch_row)
        hint = QLabel("Analyze clones the selected GitHub branch, auto-detects dependency files, and runs JFrog CVE audit.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #888; font-style: italic; padding: 2px;")
        lay.addRow("", hint)
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
        self._capture_build_logs = QCheckBox("Capture Before/After Build Logs (batch only)")
        self._capture_build_logs.setToolTip(
            "Batch runs only. Runs an extra full build against the "
            "pre-remediation file to leave clean build-log-before.txt/"
            "build-log-after.txt artifacts. Slower per repo -- intended for "
            "verification runs, not routine production batches. Has no "
            "effect on the single-repo Analyze action."
        )
        fl.addWidget(self._capture_build_logs)
        fl.addStretch()
        lay.addRow("Flags:", flags)

        self._workers = QSpinBox()
        self._workers.setRange(1, 32)
        self._workers.setValue(8)
        lay.addRow("Workers:", self._workers)

        self._columns_edit = QLineEdit("")

        self._log_dir = QLineEdit(_DEFAULT_LOG_DIR)
        lay.addRow("Log Dir:", self._log_dir)
        return g

    def _make_advanced_group(self) -> QGroupBox:
        g = QGroupBox("Advanced  (JFrog / Artifactory / npm)")
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
        self._xray_url = QLineEdit(_env("JFROG_XRAY_HOST"))
        self._xray_url.setPlaceholderText("https://company.jfrog.io")
        lay.addRow("Artifactory URL:", self._art_src)
        lay.addRow("Artifactory Repo:", self._art_repo)
        lay.addRow("Artifactory User:", self._art_user)
        lay.addRow("Artifactory Pass:", self._art_pass)
        lay.addRow("JFrog/Xray URL:", self._xray_url)

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
        self._gradle_timeout.setValue(150)
        self._gradle_timeout.setSuffix(" s")
        lay.addRow("Gradle Timeout:", self._gradle_timeout)
        return g

    # ── interactions ──────────────────────────────────────────────────────────

    def _repo_project_dir(self) -> str:
        from shared.github import repo_name_from_url

        checkout_parent = self._checkout_dir.text().strip()
        github_url = self._github_url.text().strip()
        if not checkout_parent or not github_url:
            return ""
        return str(Path(checkout_parent) / repo_name_from_url(github_url))

    def _on_github_url_changed(self, text: str):
        if text.strip() != self._branch_url:
            self._branch_combo.blockSignals(True)
            self._branch_combo.clear()
            self._branch_combo.lineEdit().setPlaceholderText("(default branch)")
            self._branch_combo.blockSignals(False)
            self._branch_url = ""

    def _fetch_branches(self):
        github_url = self._github_url.text().strip()
        if not github_url:
            self._log_err("'GitHub Repo URL' is required to fetch branches.")
            return
        current = self._branch_combo.currentText().strip()
        self._fetch_branches_btn.setEnabled(False)
        self._fetch_branches_btn.setText("Fetching...")
        try:
            from shared.github import list_github_branches
            branches = list_github_branches(github_url)
        except Exception as exc:
            self._log_err(f"Failed to fetch branches: {exc}")
            return
        finally:
            self._fetch_branches_btn.setEnabled(True)
            self._fetch_branches_btn.setText("Fetch Branches")
        self._branch_combo.blockSignals(True)
        self._branch_combo.clear()
        self._branch_combo.addItem("")
        self._branch_combo.lineEdit().setPlaceholderText("(default branch)")
        self._branch_combo.addItems(branches)
        if current:
            idx = self._branch_combo.findText(current)
            if idx >= 0:
                self._branch_combo.setCurrentIndex(idx)
            else:
                self._branch_combo.setEditText(current)
        self._branch_url = github_url
        self._branch_combo.blockSignals(False)
        self._log_info(f"Fetched {len(branches)} branch(es).")

    def _build_shared_settings(self) -> dict:
        log_dir_raw = self._log_dir.text().strip() or _DEFAULT_LOG_DIR
        app_dir = str(Path(__file__).parent.parent)
        if os.path.isabs(log_dir_raw):
            log_dir = normalize_log_dir(log_dir_raw, app_dir)
        else:
            log_dir = normalize_log_dir(str(Path(app_dir) / log_dir_raw), app_dir)
        return {
            "checkout_dir": self._checkout_dir.text().strip(),
            "log_dir": log_dir,
            "workers": self._workers.value(),
            "npm_cmd": self._npm_cmd.text().strip() or "npm",
            "npm_timeout": self._npm_timeout.value(),
            "npm_registry": self._npm_registry.text().strip() or None,
            "gradle_timeout": self._gradle_timeout.value(),
            "enable_failure_isolation": False,
            "skip_block_check": self._skip_bc.isChecked(),
            "capture_build_logs": self._capture_build_logs.isChecked(),
            "artifactory_source": self._art_src.text().strip(),
            "artifactory_repo": self._art_repo.text().strip(),
            "artifactory_username": self._art_user.text().strip(),
            "artifactory_password": self._art_pass.text(),
        }

    def _build_config(self) -> dict | None:
        def _req(w, name: str) -> str | None:
            v = w.text().strip()
            if not v:
                self._log_err(f"'{name}' is required.")
            return v or None

        github_url = _req(self._github_url, "GitHub Repo URL")
        if not github_url:
            return None

        log_dir_raw = self._log_dir.text().strip() or _DEFAULT_LOG_DIR
        app_dir = str(Path(__file__).parent.parent)
        if os.path.isabs(log_dir_raw):
            log_dir = normalize_log_dir(log_dir_raw, app_dir)
        else:
            log_dir = normalize_log_dir(str(Path(app_dir) / log_dir_raw), app_dir)
        return {
            "github_url": github_url,
            "checkout_dir": self._checkout_dir.text().strip(),
            "branch": self._branch_combo.currentText().strip(),
            "dep_managers": [],
            "proj_dir": self._repo_project_dir(),
            "skip_block_check": self._skip_bc.isChecked(),
            # capture_build_logs is intentionally omitted here: the single-
            # repo "Analyze" path (ui/worker.py) is a separate implementation
            # that never calls quick_update.py's write/validate flow where
            # build-log capture is wired in -- setting the key here would be
            # silently ignored rather than doing anything.
            "workers": self._workers.value(),
            "columns": self._columns_edit.text().strip(),
            "log_dir": log_dir,
            "artifactory_source": self._art_src.text().strip(),
            "artifactory_repo": self._art_repo.text().strip(),
            "artifactory_username": self._art_user.text().strip(),
            "artifactory_password": self._art_pass.text(),
            "xray_url": self._xray_url.text().strip(),
            "npm_registry": self._npm_registry.text().strip() or None,
            "npm_cmd": self._npm_cmd.text().strip() or "npm",
            "npm_timeout": self._npm_timeout.value(),
            "gradle_timeout": self._gradle_timeout.value(),
            "enable_failure_isolation": False,
            "jfrog_timeout": 600,
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
        self._github_repo_btn.setEnabled(False)
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

    def _run_phase2(self):
        if not self._results:
            self._log_warn("No analysis results - run Analyze first.")
            return

        self._results.setdefault("cfg", {})
        self._results["cfg"]["enable_failure_isolation"] = True
        self._log_info("Phase 2 isolation enabled.")
        self._write_output()

    def _write_output(self):
        if self._write_worker and self._write_worker.isRunning():
            return
        if not self._results:
            self._log_warn("No analysis results - run Analyze first.")
            return

        self._write_btn.setEnabled(False)
        self._analyze_btn.setEnabled(False)
        self._stop_btn.setEnabled(False)
        self._progress_bar.setRange(0, 0)
        self._progress_label.setText("Writing output...")
        self._tabs.setCurrentIndex(0)
        self._log_info("Write Output started.")

        self._write_worker = WriteOutputWorker(self._results)
        self._write_worker.log_line.connect(self._append)
        self._write_worker.err_line.connect(self._append_err)
        self._write_worker.progress.connect(self._on_progress)
        self._write_worker.file_done.connect(self._on_write_file_done)
        self._write_worker.all_done.connect(self._on_write_done)
        self._write_worker.start()

    def closeEvent(self, a0):
        if self._worker and self._worker.isRunning():
            self._worker.abort()
        if self._batch_tab._worker and self._batch_tab._worker.isRunning():
            self._batch_tab._worker.abort()
        if a0:
            a0.accept()

    def _stop_pipeline(self):
        if self._worker:
            self._worker.abort()
        self._log_warn("Stop requested — will halt after current step.")

    def _open_github_repo(self):
        if self._results and self._results.get("github_url"):
            open_url(self._results["github_url"])

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
        self._phase2_btn.setEnabled(True)
        self._github_repo_btn.setEnabled(True)

        self._populate_changes_table(results)
        self._populate_skipped_table(results)
        self._populate_cves_table(results)

        all_pkgs: set = set()
        for fr in results.get("file_results", []):
            for ch in fr.get("display_changes", []):
                if ch.get("package"):
                    all_pkgs.add(ch["package"])
            for sk in fr.get("skipped_display", []):
                if sk.get("package"):
                    all_pkgs.add(sk["package"])

        if hasattr(self, "_related_highlighter"):
            self._related_highlighter.set_packages(all_pkgs)

        total_changes = sum(
            len(fr.get("display_changes", [])) for fr in results.get("file_results", [])
        )
        total_skipped = sum(
            len(fr.get("skipped_display", [])) for fr in results.get("file_results", [])
        )
        jfrog = results.get("jfrog_result", {}) or {}
        vuln_count = jfrog.get("vulnerability_count")
        jfrog_note = (
            f" JFrog audit vulnerabilities: {vuln_count}."
            if vuln_count is not None
            else ""
        )

        self._append_colored(
            f"✓  Analysis complete — {total_changes} change(s), {total_skipped} skipped."
            f"{jfrog_note} See Changes tab and JFrog audit log.",
            "#4ec9b0",
        )
        self._tabs.setCurrentIndex(1)

    def _on_all_done(self):
        self._drain_pending_log_lines()
        self._analyze_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(100)
        self._progress_label.setText("Done")
    def _on_write_file_done(self, path: str, ok: bool):
        if ok:
            self._append_colored(f"Write completed for {path}", "#4ec9b0")
        else:
            self._append_err(f"Write failed for {path}")

    def _on_write_done(self, any_written: bool):
        self._drain_pending_log_lines()
        self._analyze_btn.setEnabled(True)
        self._write_btn.setEnabled(bool(self._results))
        self._phase2_btn.setEnabled(bool(self._results))
        self._stop_btn.setEnabled(False)
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(100)
        self._progress_label.setText("Done")
        if any_written:
            self._log_info("All files written.")
        else:
            self._log_warn("Nothing to write.")

        if self._results:
            try:
                log_dir = (self._results.get("cfg") or {}).get("log_dir")
                report_path = generate_report(self._results, log_dir=log_dir)
                self._append_colored(f"Report generated → {report_path}", "#4ec9b0")
            except Exception as exc:
                self._append_err(f"Report generation failed: {exc}")


    # ── parameter persistence ─────────────────────────────────────────────────
    def _load_params(self):
        import json

        try:
            data = json.loads(_PARAMS_FILE.read_text())
        except Exception:
            return

        for attr, key, _ in _PARAM_LINES:
            if key in data and hasattr(self, attr):
                widget = getattr(self, attr)
                if hasattr(widget, "setText"):
                    widget.setText(str(data[key]))
                elif hasattr(widget, "setEditText"):
                    widget.setEditText(str(data[key]))

        for attr, key, _ in _PARAM_CHECKS:
            if key in data and hasattr(self, attr):
                getattr(self, attr).setChecked(bool(data[key]))

        for attr, key, _ in _PARAM_SPINS:
            if key in data and hasattr(self, attr):
                with contextlib.suppress(TypeError, ValueError):
                    getattr(self, attr).setValue(int(data[key]))

    def _save_params(self):
        import json
        data: dict = {}

        for attr, key, _ in _PARAM_LINES:
            if hasattr(self, attr):
                widget = getattr(self, attr)
                if hasattr(widget, "text"):
                    data[key] = widget.text().strip()
                elif hasattr(widget, "currentText"):
                    data[key] = widget.currentText().strip()

        for attr, key, _ in _PARAM_CHECKS:
            if hasattr(self, attr):
                data[key] = getattr(self, attr).isChecked()

        for attr, key, _ in _PARAM_SPINS:
            if hasattr(self, attr):
                data[key] = getattr(self, attr).value()

        with contextlib.suppress(Exception):
            _PARAMS_FILE.write_text(json.dumps(data, indent=2))

    def _reset_params(self):
        with contextlib.suppress(Exception):
            _PARAMS_FILE.unlink(missing_ok=True)

        for attr, _key, default in _PARAM_LINES:
            if hasattr(self, attr):
                widget = getattr(self, attr)
                if hasattr(widget, "setText"):
                    widget.setText(str(default))
                elif hasattr(widget, "setEditText"):
                    widget.setEditText(str(default))

        for attr, _key, default in _PARAM_CHECKS:
            if hasattr(self, attr):
                getattr(self, attr).setChecked(bool(default))

        for attr, _key, default in _PARAM_SPINS:
            if hasattr(self, attr):
                getattr(self, attr).setValue(int(default))


        self._log_info("Parameters reset to defaults.")

    # ── context menu ──────────────────────────────────────────────────────────

    def _on_changes_context_menu(self, pos):
        if not self._results:
            return
        menu = QMenu(self)
        github_url = self._results.get("github_url", "")
        if github_url:
            act = menu.addAction("Open GitHub Repo ↗")
            act.triggered.connect(lambda: open_url(github_url))
        jfrog_log = self._results.get("jfrog_result", {}).get("json_path", "")
        if jfrog_log:
            act = menu.addAction("Show JFrog audit log path")
            act.triggered.connect(lambda: self._log_info(f"JFrog audit log: {jfrog_log}"))
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
        self._show_related_tasks(pkg, [])

    def _on_related_task_selected(self, current: QListWidgetItem | None, _prev):
        # Kept for the related-list signal. The GitHub/JFrog flow no longer
        # populates  task items, so selecting a related item is optional/no-op.
        if current is None:
            return
        data = current.data(Qt.ItemDataRole.UserRole)
        if isinstance(data, dict):
            self._related_detail.setPlainText("\n".join(str(v) for v in data.values() if v))

    def _show_related_tasks(self, package_name: str, task_ids: list):
        self._related_list.clear()
        self._related_detail.clear()
        self._related_highlighter.set_packages({package_name} if package_name else set())
        self._related_header.setText(f"Package context for '{package_name}'")
        jfrog_log = (self._results or {}).get("jfrog_result", {}).get("json_path", "")
        lines = [
            f"Package: {package_name}",
        ]
        if jfrog_log:
            lines.append(f"JFrog audit log: {jfrog_log}")
        self._related_detail.setPlainText("\n".join(lines))

    # ── table / task population ───────────────────────────────────────────────

    def _populate_cves_table(self, results: dict):
        self._cves_table.setRowCount(0)
        jfrog = results.get("jfrog_result", {}) or {}
        rows = jfrog.get("vulnerable_components") or []

        if rows:
            self._cves_hint.hide()
        else:
            self._cves_hint.setText("No CVEs found by JFrog audit.")
            self._cves_hint.show()

        ecosystem_colors = {
            "npm": "#569cd6",
            "maven": "#ce9178",
        }

        for r in rows:
            row = self._cves_table.rowCount()
            self._cves_table.insertRow(row)

            ecosystem = str(r.get("ecosystem", ""))
            package = str(r.get("package", ""))
            version = str(r.get("version", ""))
            component_id = str(r.get("component_id", ""))
            cves = r.get("cves", [])
            cve_text = ", ".join(str(cve) for cve in cves) if isinstance(cves, list) else str(cves)

            ecosystem_item = QTableWidgetItem(ecosystem)
            ecosystem_item.setForeground(QColor(ecosystem_colors.get(ecosystem, "#d4d4d4")))
            ecosystem_item.setData(Qt.ItemDataRole.UserRole, r)
            self._cves_table.setItem(row, 0, ecosystem_item)

            package_item = QTableWidgetItem(package)
            package_item.setData(Qt.ItemDataRole.UserRole, r)
            self._cves_table.setItem(row, 1, package_item)

            version_item = QTableWidgetItem(version)
            version_item.setForeground(QColor("#dcdcaa"))
            version_item.setData(Qt.ItemDataRole.UserRole, r)
            self._cves_table.setItem(row, 2, version_item)

            cve_item = QTableWidgetItem(cve_text)
            cve_item.setForeground(QColor("#f44747"))
            cve_item.setData(Qt.ItemDataRole.UserRole, r)
            self._cves_table.setItem(row, 3, cve_item)

            component_item = QTableWidgetItem(component_id)
            component_item.setForeground(QColor("#888"))
            component_item.setData(Qt.ItemDataRole.UserRole, r)
            self._cves_table.setItem(row, 4, component_item)

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

                source_text = "JFrog" if ch.get("change_type") in {"block-fix", "gradle", "gradle-force"} or ch.get("remediation_guided") else ""
                source_item = QTableWidgetItem(source_text)
                if source_text:
                    source_item.setForeground(QColor("#4ec9b0"))
                    source_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self._changes_table.setItem(row, 5, source_item)

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

    # ── log helpers ───────────────────────────────────────────────────────────

    def _append_colored(self, text: str, color: str):
        self._pending_log_lines.append((text, color))

    def _flush_pending_log_lines(self):
        if not self._pending_log_lines:
            return

        scrollbar = self._log.verticalScrollBar()
        was_near_bottom = (
            scrollbar.maximum() - scrollbar.value() < 80
        )

        batch = self._pending_log_lines[:250]
        del self._pending_log_lines[:250]

        cursor = self._log.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        for line, color in batch:
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            cursor.setCharFormat(fmt)
            cursor.insertText(line + "\n")

        self._log.setTextCursor(cursor)
        if was_near_bottom:
            scrollbar.setValue(scrollbar.maximum())

    def _drain_pending_log_lines(self):
        while self._pending_log_lines:
            self._flush_pending_log_lines()
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
