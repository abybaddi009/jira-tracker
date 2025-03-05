from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon

from jira_integration import JiraCredentialsDialog, setup_jira_credentials
from logging_setup import get_logger
from utils import resource_path

logger = get_logger(__name__)


def setup_tray_icon(app, widget):
    """
    Set up the system tray icon and its menu.

    Args:
        app: The QApplication instance
        widget: The main widget to control

    Returns:
        tray_icon: The created QSystemTrayIcon or None if not available
    """
    if not QSystemTrayIcon.isSystemTrayAvailable():
        logger.warning("System tray is not available on this system")
        return None

    # Create tray icon
    tray_icon = QSystemTrayIcon(QIcon(resource_path("static/icon.png")), app)
    tray_icon.setToolTip("JIRA TimeTracker")

    # Create tray menu
    tray_menu = QMenu()

    # Add JIRA credentials configuration option to tray menu
    jira_config_action = tray_menu.addAction("Configure JIRA")
    jira_config_action.triggered.connect(lambda: JiraCredentialsDialog().exec())

    # Create show/hide action that toggles based on widget visibility
    show_hide_action = tray_menu.addAction("Hide")

    def update_show_hide_action(visible):
        show_hide_action.setText("Hide" if visible else "Show")

    def toggle_visibility():
        if widget.isVisible():
            widget.hide()
        else:
            widget.show()

    show_hide_action.triggered.connect(toggle_visibility)
    widget.visibility_changed.connect(update_show_hide_action)

    # Initialize the action text based on current visibility
    update_show_hide_action(widget.isVisible())

    def quit_application():
        app.quit()  # Just call quit directly on the QApplication instance

    quit_action = tray_menu.addAction("Quit")
    quit_action.triggered.connect(quit_application)

    # Set the menu and show the tray icon
    tray_icon.setContextMenu(tray_menu)
    tray_icon.show()

    # Connect double-click to show/hide
    tray_icon.activated.connect(widget._handle_tray_activation)

    logger.info("System tray icon set up successfully")
    return tray_icon
