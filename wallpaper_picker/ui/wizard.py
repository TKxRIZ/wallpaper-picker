import os
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QVBoxLayout, QWizard, QWizardPage,
)

from ..config import Config, validate_setup
from ..constants import IS_ATOMIC, DISTRO_NAME
from ..i18n import t
from .dialogs import BuildDialog

PAGE_WELCOME = 0
PAGE_MODE    = 1
PAGE_BINARY  = 2
PAGE_ASSETS  = 3
PAGE_FINISH  = 4


class WelcomePage(QWizardPage):
    def __init__(self, cfg: Config):
        super().__init__()
        self._cfg = cfg
        self.setTitle(t("wiz_welcome_title"))
        self.setSubTitle(t("wiz_welcome_sub"))

        layout = QVBoxLayout(self)
        ptype  = t("info_atomic") if IS_ATOMIC else t("info_traditional")
        info   = QLabel(t("wiz_welcome_body", distro=DISTRO_NAME, ptype=ptype))
        info.setWordWrap(True)
        layout.addWidget(info)

        if not validate_setup(cfg):
            ok = QLabel(t("wiz_already_ok"))
            ok.setStyleSheet("color:#4caf50; font-weight:bold; padding-top:12px;")
            layout.addWidget(ok)

        layout.addStretch()


class ModePage(QWizardPage):
    def __init__(self, cfg: Config):
        super().__init__()
        self._cfg = cfg
        self.setTitle(t("wiz_mode_title"))
        self.setSubTitle(t("wiz_mode_sub"))

        layout = QFormLayout(self)

        self._mode = QComboBox()
        self._mode.currentTextChanged.connect(self._on_mode)
        layout.addRow(t("wiz_mode_label"), self._mode)

        self._container = QLineEdit(cfg.container)
        layout.addRow(t("wiz_container_label"), self._container)

        self._desc = QLabel()
        self._desc.setWordWrap(True)
        self._desc.setStyleSheet("color:#aaa; font-size:11px; padding-top:8px;")
        layout.addRow("", self._desc)

        self._populate_modes()

    def _populate_modes(self):
        self._mode.clear()
        available = []
        for runtime, mode in [("distrobox", "distrobox"), ("toolbox", "toolbox")]:
            if Path(f"/usr/bin/{runtime}").exists():
                available.append((f"{mode}{t('wiz_mode_recommended')}", mode))
        available += [
            (t("wiz_mode_direct"), "direct"),
            (t("wiz_mode_custom"), "custom"),
        ]
        for label, val in available:
            self._mode.addItem(label, val)
        for i in range(self._mode.count()):
            if self._mode.itemData(i) == self._cfg.mode:
                self._mode.setCurrentIndex(i)
                break

    def _on_mode(self, _):
        mode = self._mode.currentData()
        descs = {
            "distrobox": t("wiz_desc_distrobox"),
            "toolbox":   t("wiz_desc_toolbox"),
            "direct":    t("wiz_desc_direct"),
            "custom":    t("wiz_desc_custom"),
        }
        self._desc.setText(descs.get(mode or "", ""))
        self._container.setEnabled(mode in ("distrobox", "toolbox"))

    def initializePage(self):
        self._on_mode(None)

    def validatePage(self) -> bool:
        mode      = self._mode.currentData()
        container = self._container.text().strip()
        if mode in ("distrobox", "toolbox") and not container:
            QMessageBox.warning(self, t("dlg_setup_incomplete"), t("wiz_err_container"))
            return False
        self._cfg.mode      = mode
        self._cfg.container = container
        return True


class BinaryPage(QWizardPage):
    def __init__(self, cfg: Config):
        super().__init__()
        self._cfg      = cfg
        self._complete = False
        self._test_worker: Optional[object] = None
        self.setTitle(t("wiz_binary_title"))
        self.setSubTitle(t("wiz_binary_sub"))
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        path_row = QHBoxLayout()
        self._path = QLineEdit(self._cfg.binary)
        self._path.setPlaceholderText(
            "/home/user/wallpaper-picker/linux-wallpaperengine/build/output/linux-wallpaperengine"
        )
        self._path.textChanged.connect(self._on_path_changed)
        detect_btn = QPushButton(t("btn_autodetect"))
        detect_btn.clicked.connect(self._autodetect)
        browse_btn = QPushButton("…")
        browse_btn.setFixedWidth(30)
        browse_btn.clicked.connect(self._browse)
        path_row.addWidget(self._path)
        path_row.addWidget(detect_btn)
        path_row.addWidget(browse_btn)
        layout.addLayout(path_row)

        test_row = QHBoxLayout()
        self._test_btn    = QPushButton(t("btn_test_binary"))
        self._test_btn.clicked.connect(self._test)
        self._test_result = QLabel("")
        self._test_result.setWordWrap(True)
        test_row.addWidget(self._test_btn)
        test_row.addWidget(self._test_result, stretch=1)
        layout.addLayout(test_row)

        from PySide6.QtWidgets import QFrame
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color:#444;")
        layout.addWidget(sep)

        build_lbl = QLabel(t("wiz_build_label"))
        build_lbl.setWordWrap(True)
        layout.addWidget(build_lbl)

        self._build_btn = QPushButton(t("btn_build_lwe"))
        self._build_btn.clicked.connect(self._open_build)
        layout.addWidget(self._build_btn)

        layout.addStretch()

    def initializePage(self):
        path = self._path.text().strip()
        if path and Path(path).exists() and os.access(path, os.X_OK):
            self._set_ok(True, t("wiz_binary_exists"))

    def _autodetect(self):
        tmp = Config(binary="", assets_dir=self._cfg.assets_dir)
        tmp.autodetect()
        if tmp.binary:
            self._path.setText(tmp.binary)
            self._test()
        else:
            self._test_result.setText(t("wiz_autodetect_fail"))

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(self, t("wiz_binary_title"))
        if path:
            self._path.setText(path)

    def _on_path_changed(self, text: str):
        if not text.strip():
            self._set_ok(False, "")

    def _test(self):
        path = self._path.text().strip()
        if not path:
            self._test_result.setText(t("wiz_no_path"))
            return
        self._test_btn.setEnabled(False)
        self._test_result.setText(t("test_running"))
        from ..workers import TestBinaryWorker
        tmp_cfg = Config(mode=self._cfg.mode, container=self._cfg.container, binary=path)
        self._test_worker = TestBinaryWorker(tmp_cfg.test_cmd())
        self._test_worker.result.connect(self._on_test)
        self._test_worker.start()

    def _on_test(self, ok: bool, msg: str):
        self._test_btn.setEnabled(True)
        self._set_ok(ok, t("wiz_test_ok") if ok else t("wiz_test_fail", msg=msg[:120]))
        if ok:
            self._test_result.setToolTip(msg)

    def _set_ok(self, ok: bool, msg: str):
        color = "#4caf50" if ok else "#f44336"
        self._test_result.setText(f'<span style="color:{color}">{msg}</span>')
        self._complete = ok
        self.completeChanged.emit()

    def _open_build(self):
        dlg = BuildDialog(self._cfg.container, self)
        dlg.binary_built.connect(self._on_built)
        dlg.exec()

    def _on_built(self, path: str):
        self._path.setText(path)
        self._test()

    def isComplete(self) -> bool:
        return self._complete

    def validatePage(self) -> bool:
        self._cfg.binary = self._path.text().strip()
        return True


class AssetsPage(QWizardPage):
    def __init__(self, cfg: Config):
        super().__init__()
        self._cfg      = cfg
        self._complete = False
        self.setTitle(t("wiz_assets_title"))
        self.setSubTitle(t("wiz_assets_sub"))
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(t("wiz_assets_hint")))

        path_row = QHBoxLayout()
        self._path = QLineEdit(self._cfg.assets_dir)
        self._path.setPlaceholderText(t("wiz_assets_placeholder"))
        self._path.textChanged.connect(self._validate_path)
        detect_btn = QPushButton(t("btn_autodetect"))
        detect_btn.clicked.connect(self._autodetect)
        browse_btn = QPushButton("…")
        browse_btn.setFixedWidth(30)
        browse_btn.clicked.connect(self._browse)
        path_row.addWidget(self._path)
        path_row.addWidget(detect_btn)
        path_row.addWidget(browse_btn)
        layout.addLayout(path_row)

        self._status = QLabel("")
        self._status.setWordWrap(True)
        layout.addWidget(self._status)
        layout.addStretch()

    def initializePage(self):
        self._validate_path(self._path.text())

    def _autodetect(self):
        tmp = Config(binary=self._cfg.binary, assets_dir="")
        tmp.autodetect()
        if tmp.assets_dir:
            self._path.setText(tmp.assets_dir)
        else:
            self._status.setText(t("wiz_assets_detect_fail"))

    def _browse(self):
        path = QFileDialog.getExistingDirectory(self, t("wiz_assets_title"))
        if path:
            self._path.setText(path)

    def _validate_path(self, text: str):
        p = Path(text.strip())
        if not text.strip():
            self._set_ok(False, "")
            return
        if not p.is_dir():
            self._set_ok(False, t("wiz_assets_not_dir", p=text))
            return
        missing = [f for f in ("shaders", "materials", "effects") if not (p / f).exists()]
        if missing:
            self._set_ok(False, t("wiz_assets_invalid", missing=", ".join(missing)))
            return
        self._set_ok(True, t("wiz_assets_ok"))

    def _set_ok(self, ok: bool, msg: str):
        color = "#4caf50" if ok else "#f44336"
        self._status.setText(f'<span style="color:{color}">{msg}</span>')
        self._complete = ok
        self.completeChanged.emit()

    def isComplete(self) -> bool:
        return self._complete

    def validatePage(self) -> bool:
        self._cfg.assets_dir = self._path.text().strip()
        return True


class FinishPage(QWizardPage):
    def __init__(self, cfg: Config):
        super().__init__()
        self._cfg = cfg
        self.setTitle(t("wiz_finish_title"))
        self.setSubTitle(t("wiz_finish_sub"))
        self._layout  = QVBoxLayout(self)
        self._summary = QLabel()
        self._summary.setWordWrap(True)
        self._layout.addWidget(self._summary)
        self._layout.addStretch()

    def initializePage(self):
        lines = [t("wiz_finish_config"), t("wiz_finish_mode", v=self._cfg.mode)]
        if self._cfg.mode in ("distrobox", "toolbox"):
            lines.append(t("wiz_finish_container", v=self._cfg.container))
        lines += [
            t("wiz_finish_binary", v=self._cfg.binary),
            t("wiz_finish_assets", v=self._cfg.assets_dir),
            t("wiz_finish_done"),
        ]
        self._summary.setText("<br>".join(lines))


class SetupWizard(QWizard):
    setup_complete = Signal()

    def __init__(self, cfg: Config, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.setWindowTitle(t("wiz_title"))
        self.setWizardStyle(QWizard.WizardStyle.ClassicStyle)
        self.setOption(QWizard.WizardOption.NoBackButtonOnStartPage)
        self.resize(720, 520)

        self.setPage(PAGE_WELCOME, WelcomePage(cfg))
        self.setPage(PAGE_MODE,    ModePage(cfg))
        self.setPage(PAGE_BINARY,  BinaryPage(cfg))
        self.setPage(PAGE_ASSETS,  AssetsPage(cfg))
        self.setPage(PAGE_FINISH,  FinishPage(cfg))
        self.setStartId(PAGE_WELCOME)

        self.button(QWizard.WizardButton.FinishButton).clicked.connect(self._on_finish)

    def _on_finish(self):
        self.cfg.save()
        self.setup_complete.emit()
