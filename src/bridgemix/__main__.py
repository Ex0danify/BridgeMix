"""Entry point: python -m bridgemix"""

import argparse
import sys
from pathlib import Path

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from bridgemix import __version__
from bridgemix.gui.main_window import MainWindow
from bridgemix.theme import APP_STYLESHEET


def _smoke_test(app: QApplication, report: Path | None) -> int:
    """Build the whole UI once and exit, for checking a packaged build on CI.

    Fails if the REST plugin's dependencies didn't make it into the bundle. The
    result also goes to *report*, since a windowed Windows build has no console.
    """
    from bridgemix.plugins.builtins.remote_api.server import dependencies_available

    window = MainWindow()
    window.show()
    QTimer.singleShot(0, app.quit)
    app.exec()
    ok = dependencies_available()
    message = (
        f"BridgeMix {__version__} smoke test ok"
        if ok
        else "smoke test failed: the REST API dependencies are missing"
    )
    if report is not None:
        report.write_text(message + "\n", encoding="utf-8")
    print(message, file=sys.stdout if ok else sys.stderr)
    return 0 if ok else 1


def main() -> None:
    parser = argparse.ArgumentParser(prog="bridgemix", description="Roland Bridge Cast controller")
    parser.add_argument("--version", action="version", version=f"BridgeMix {__version__}")
    parser.add_argument(
        "--smoke-test", action="store_true", help="start the UI once and exit (for packaged builds)"
    )
    parser.add_argument("--smoke-report", type=Path, help="write the --smoke-test result to a file")
    args, qt_args = parser.parse_known_args()

    app = QApplication([sys.argv[0], *qt_args])
    app.setApplicationName("BridgeMix")
    app.setOrganizationName("Ex0danify")
    # Wayland/KDE picks the taskbar icon by matching the window's app_id to an
    # installed .desktop file — the Qt window icon alone isn't used there. This
    # sets app_id to the reverse-DNS application id; it must match the Flatpak
    # app-id and the installed <app-id>.desktop.
    app.setDesktopFileName("io.github.ex0danify.BridgeMix")
    app.setStyleSheet(APP_STYLESHEET)

    if args.smoke_test:
        sys.exit(_smoke_test(app, args.smoke_report))

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
