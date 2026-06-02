import sys

from PySide6.QtWidgets import QApplication

from .ui.theme import setup_palette
from .ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("wallpaper-picker")
    app.setApplicationDisplayName("Wallpaper Engine – Linux")
    app.setOrganizationName("TKxRIZ")
    app.setQuitOnLastWindowClosed(True)
    setup_palette(app)

    win = MainWindow()
    win.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
