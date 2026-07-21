from __future__ import annotations

import contextlib
import json
import os
import sys
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMainWindow,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from shared.utils import normalize_log_dir
from ui.batch_tab import BatchTab

_DEFAULT_CHECKOUT = str(Path.home() / ".package_update_gui" / "repos")
_DEFAULT_LOG_DIR = str(Path(__file__).parent.parent / "logs")
_PARAMS_FILE = Path.home() / ".package_update_batch.json"

_PARAM_LINES = [
    ("_github_prefix", "github_prefix", ""),
    ("_art_src",       "artifactory_source", ""),
    ("_art_repo",      "artifactory_repo", "ins-cp-mgmt-gradle-virtual"),
    ("_art_user",      "artifactory_username", ""),
    ("_checkout_dir",  "checkout_dir", _DEFAULT_CHECKOUT),
    ("_log_dir",       "log_dir", _DEFAULT_LOG_DIR),
    ("_npm_cmd",       "npm_cmd", "npm"),
    ("_npm_registry",  "npm_registry", ""),
]
_PARAM_CHECKS = [
    ("_skip_bc", "skip_block_check", False),
]
_PARAM_SPINS = [
    ("_workers",        "workers",          8),
    ("_parallel_repos", "parallel_repos",   4),
    ("_repo_timeout",   "repo_timeout_min", 20),
    ("_npm_timeout",    "npm_timeout",      90),
    ("_gradle_timeout", "gradle_timeout",   150),
]


class QuickBatchWindow(QMainWindow):
    def __init__(self, cfg=None):
        super().__init__()
        self.setWindowTitle("Package Update — Batch Runner")
        self.resize(1100, 700)
        self._setup_ui(cfg)
        self._load_params()

    # ── layout ────────────────────────────────────────────────────────────────

    def _setup_ui(self, cfg):
        root = QWidget()
        self.setCentralWidget(root)
        from PyQt6.QtWidgets import QHBoxLayout
        root_lay = QHBoxLayout(root)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        root_lay.addWidget(splitter)

        splitter.addWidget(self._make_settings_panel(cfg))
        self._batch_tab = BatchTab(get_settings=self._build_settings)
        splitter.addWidget(self._batch_tab)
        splitter.setSizes([320, 780])

    def _make_settings_panel(self, cfg) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumWidth(280)
        scroll.setMaximumWidth(400)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        panel = QWidget()
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(8)

        def _env(key, default=""):
            return os.environ.get(key, default)

        def _cfgv(attr, default=""):
            v = getattr(cfg, attr, None) if cfg else None
            return v if v is not None else default

        # ── GitHub ──
        gh_g = QGroupBox("GitHub")
        gh_lay = QFormLayout(gh_g)
        gh_lay.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        gh_lay.setSpacing(6)
        self._github_prefix = QLineEdit()
        self._github_prefix.setPlaceholderText("https://github.com/MyOrg/")
        hint = QLabel("Short names in the table are expanded with this prefix and .git appended if missing.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #888; font-size: 10px;")
        gh_lay.addRow("Prefix:", self._github_prefix)
        gh_lay.addRow("", hint)
        lay.addWidget(gh_g)

        # ── General ──
        gen_g = QGroupBox("General")
        gen_lay = QFormLayout(gen_g)
        gen_lay.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        gen_lay.setSpacing(6)

        self._checkout_dir = QLineEdit(_cfgv("checkout_dir") or _DEFAULT_CHECKOUT)
        self._checkout_dir.setPlaceholderText("Local clone directory")
        self._log_dir = QLineEdit(_cfgv("log_dir") or _DEFAULT_LOG_DIR)
        self._workers = QSpinBox()
        self._workers.setRange(1, 32)
        self._workers.setValue(_cfgv("workers") or 8)

        self._parallel_repos = QSpinBox()
        self._parallel_repos.setRange(1, 16)
        self._parallel_repos.setValue(_cfgv("parallel_repos") or 4)
        self._parallel_repos.setToolTip("How many repos to run simultaneously")

        self._repo_timeout = QSpinBox()
        self._repo_timeout.setRange(1, 999)
        self._repo_timeout.setValue(_cfgv("repo_timeout_min") or 20)
        self._repo_timeout.setSuffix(" min")
        self._repo_timeout.setToolTip("Kill a repo run if it produces no output for this long")

        self._skip_bc = QCheckBox("Skip Block Check")
        self._skip_bc.setChecked(bool(_cfgv("skip_block_check")))

        gen_lay.addRow("Clone To:", self._checkout_dir)
        gen_lay.addRow("Log Dir:", self._log_dir)
        gen_lay.addRow("Workers:", self._workers)
        gen_lay.addRow("Parallel repos:", self._parallel_repos)
        gen_lay.addRow("Inactivity timeout:", self._repo_timeout)
        gen_lay.addRow("", self._skip_bc)
        lay.addWidget(gen_g)

        # ── JFrog / Artifactory ──
        jfrog_g = QGroupBox("JFrog / Artifactory")
        jfrog_lay = QFormLayout(jfrog_g)
        jfrog_lay.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        jfrog_lay.setSpacing(6)

        self._art_src = QLineEdit(_cfgv("artifactory_source") or _env("ARTIFACTORY_SOURCE"))
        self._art_src.setPlaceholderText("https://company.jfrog.io/artifactory")
        self._art_repo = QLineEdit(
            _cfgv("artifactory_repo") or _env("ARTIFACTORY_REPO", "ins-cp-mgmt-gradle-virtual")
        )
        self._art_user = QLineEdit(_cfgv("artifactory_username") or _env("ARTIFACTORY_USERNAME"))
        self._art_pass = QLineEdit(_cfgv("artifactory_password") or _env("ARTIFACTORY_PASSWORD"))
        self._art_pass.setEchoMode(QLineEdit.EchoMode.Password)

        jfrog_lay.addRow("Artifactory URL:", self._art_src)
        jfrog_lay.addRow("Repo:", self._art_repo)
        jfrog_lay.addRow("Username:", self._art_user)
        jfrog_lay.addRow("Password:", self._art_pass)
        lay.addWidget(jfrog_g)

        # ── npm ──
        npm_g = QGroupBox("npm")
        npm_lay = QFormLayout(npm_g)
        npm_lay.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        npm_lay.setSpacing(6)

        self._npm_cmd = QLineEdit(_cfgv("npm_cmd") or "npm")
        self._npm_registry = QLineEdit(_cfgv("npm_registry") or "")
        self._npm_registry.setPlaceholderText("(blank = use .npmrc)")
        self._npm_timeout = QSpinBox()
        self._npm_timeout.setRange(10, 600)
        self._npm_timeout.setValue(_cfgv("npm_timeout") or 90)
        self._npm_timeout.setSuffix(" s")

        npm_lay.addRow("npm Command:", self._npm_cmd)
        npm_lay.addRow("Registry:", self._npm_registry)
        npm_lay.addRow("Timeout:", self._npm_timeout)
        lay.addWidget(npm_g)

        # ── Gradle ──
        gradle_g = QGroupBox("Gradle")
        gradle_lay = QFormLayout(gradle_g)
        gradle_lay.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        gradle_lay.setSpacing(6)

        self._gradle_timeout = QSpinBox()
        self._gradle_timeout.setRange(5, 300)
        self._gradle_timeout.setValue(_cfgv("gradle_timeout") or 150)
        self._gradle_timeout.setSuffix(" s")
        gradle_lay.addRow("Timeout:", self._gradle_timeout)
        lay.addWidget(gradle_g)

        lay.addStretch()
        scroll.setWidget(panel)
        return scroll

    # ── settings ──────────────────────────────────────────────────────────────

    def _build_settings(self) -> dict:
        self._save_params()
        log_dir_raw = self._log_dir.text().strip() or _DEFAULT_LOG_DIR
        app_dir = str(Path(__file__).parent.parent)
        log_dir = normalize_log_dir(
            log_dir_raw if os.path.isabs(log_dir_raw) else str(Path(app_dir) / log_dir_raw),
            app_dir,
        )
        return {
            "github_prefix": self._github_prefix.text().strip().rstrip("/"),
            "checkout_dir": self._checkout_dir.text().strip() or _DEFAULT_CHECKOUT,
            "log_dir": log_dir,
            "workers": self._workers.value(),
            "parallel_repos": self._parallel_repos.value(),
            "repo_timeout_min": self._repo_timeout.value(),
            "npm_cmd": self._npm_cmd.text().strip() or "npm",
            "npm_timeout": self._npm_timeout.value(),
            "npm_registry": self._npm_registry.text().strip() or None,
            "gradle_timeout": self._gradle_timeout.value(),
            "skip_block_check": self._skip_bc.isChecked(),
            "artifactory_source": self._art_src.text().strip(),
            "artifactory_repo": self._art_repo.text().strip(),
            "artifactory_username": self._art_user.text().strip(),
            "artifactory_password": self._art_pass.text(),
        }

    # ── persistence ───────────────────────────────────────────────────────────

    def _load_params(self):
        try:
            data = json.loads(_PARAMS_FILE.read_text())
        except Exception:
            return
        for attr, key, _ in _PARAM_LINES:
            if key in data and hasattr(self, attr):
                getattr(self, attr).setText(str(data[key]))
        for attr, key, _ in _PARAM_CHECKS:
            if key in data and hasattr(self, attr):
                getattr(self, attr).setChecked(bool(data[key]))
        for attr, key, _ in _PARAM_SPINS:
            if key in data and hasattr(self, attr):
                with contextlib.suppress(TypeError, ValueError):
                    getattr(self, attr).setValue(int(data[key]))

    def _save_params(self):
        data: dict = {}
        for attr, key, _ in _PARAM_LINES:
            if hasattr(self, attr):
                data[key] = getattr(self, attr).text().strip()
        for attr, key, _ in _PARAM_CHECKS:
            if hasattr(self, attr):
                data[key] = getattr(self, attr).isChecked()
        for attr, key, _ in _PARAM_SPINS:
            if hasattr(self, attr):
                data[key] = getattr(self, attr).value()
        with contextlib.suppress(Exception):
            _PARAMS_FILE.write_text(json.dumps(data, indent=2))

    def closeEvent(self, event):
        self._save_params()
        event.accept()


def run_with_gui(cfg=None) -> None:
    from PyQt6.QtWidgets import QApplication

    from ui.widgets import APP_STYLESHEET, dark_palette

    app = QApplication(sys.argv[:1])
    app.setStyle("Fusion")
    app.setPalette(dark_palette())
    app.setStyleSheet(APP_STYLESHEET)

    win = QuickBatchWindow(cfg)
    win.show()
    sys.exit(app.exec())
