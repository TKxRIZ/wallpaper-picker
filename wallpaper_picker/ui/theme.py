from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


def setup_palette(app: QApplication):
    app.setStyle("Fusion")
    p   = QPalette()
    bg  = QColor(30,  30,  46)
    bg2 = QColor(24,  24,  37)
    fg  = QColor(205, 214, 244)
    sub = QColor(166, 173, 200)
    btn = QColor(49,  50,  68)
    acc = QColor(137, 180, 250)

    p.setColor(QPalette.ColorRole.Window,          bg)
    p.setColor(QPalette.ColorRole.WindowText,      fg)
    p.setColor(QPalette.ColorRole.Base,            bg2)
    p.setColor(QPalette.ColorRole.AlternateBase,   bg)
    p.setColor(QPalette.ColorRole.Text,            fg)
    p.setColor(QPalette.ColorRole.PlaceholderText, sub)
    p.setColor(QPalette.ColorRole.Button,          btn)
    p.setColor(QPalette.ColorRole.ButtonText,      fg)
    p.setColor(QPalette.ColorRole.Highlight,       acc)
    p.setColor(QPalette.ColorRole.HighlightedText, bg)
    p.setColor(QPalette.ColorRole.Link,            acc)
    p.setColor(QPalette.ColorRole.ToolTipBase,     btn)
    p.setColor(QPalette.ColorRole.ToolTipText,     fg)

    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, sub)
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, sub)
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text,       sub)

    app.setPalette(p)
    app.setStyleSheet(
        "QToolTip{background:#313244;color:#cdd6f4;border:1px solid #585b70;padding:4px;}"
        "QScrollBar:vertical{width:8px;background:#1e1e2e;border-radius:4px;}"
        "QScrollBar::handle:vertical{background:#45475a;border-radius:4px;min-height:24px;}"
        "QScrollBar::handle:vertical:hover{background:#585b70;}"
        "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}"
        "QScrollBar:horizontal{height:8px;background:#1e1e2e;border-radius:4px;}"
        "QScrollBar::handle:horizontal{background:#45475a;border-radius:4px;min-width:24px;}"
        "QTabBar::tab{padding:6px 14px;border-radius:4px 4px 0 0;}"
        "QTabBar::tab:selected{background:#313244;}"
        "QPushButton{border-radius:5px;padding:4px 10px;}"
        "QPushButton:hover{background:#45475a;}"
        "QLineEdit{border:1px solid #313244;border-radius:5px;padding:3px 6px;}"
        "QLineEdit:focus{border-color:#89b4fa;}"
        "QGroupBox{border:1px solid #313244;border-radius:6px;margin-top:8px;padding-top:6px;}"
        "QGroupBox::title{subcontrol-origin:margin;left:8px;}"
    )
