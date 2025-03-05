import os
import sys

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from alchemy import init_db
from gui.widget import TimeTrackerWidget
from jira_integration import setup_jira_credentials
from logging_setup import get_logger
from time_tracking import pause_task, resume_task, start_task, stop_task
from tray_setup import setup_tray_icon
from utils import resource_path


class TimeTrackerApp:
    def __init__(self):
        self.logger = get_logger(__name__)
        self.current_task_id = None

        # Initialize Qt application
        self.app = QApplication(sys.argv)

        # Setup JIRA credentials
        if not setup_jira_credentials():
            self.logger.error("JIRA credentials setup failed")
            sys.exit(1)

        # Set application icon
        icon_path = resource_path("static/icon.png")
        if os.path.exists(icon_path):
            self.app.setWindowIcon(QIcon(icon_path))
        else:
            self.logger.warning(f"Icon not found at: {icon_path}")

        self.widget = TimeTrackerWidget()

        # Setup system tray
        self.tray_icon = setup_tray_icon(self.app, self.widget)

        # Connect widget signals
        self.widget.start_clicked.connect(self.handle_start)
        self.widget.pause_clicked.connect(self.handle_pause)
        self.widget.stop_clicked.connect(self.handle_stop)
        self.widget.expand_clicked.connect(self.handle_expand)

        # Add cleanup handler
        self.app.aboutToQuit.connect(self.cleanup)

        # Track if we're really quitting
        self.is_quitting = False

    def handle_start(self):
        try:
            task_name, ticket_number = self.widget.get_task_and_ticket()
            if task_name == "Select a task":
                return

            # Check if there's a paused task
            if self.current_task_id:
                # Resume existing task
                resume_task(self.current_task_id)
            else:
                # Start new task
                self.current_task_id = start_task(task_name, jira_key=ticket_number)

            self.widget.set_task_name(task_name)
            self.widget.update_button_states(task_active=True)
            self.widget.start_timer()
            self.logger.info(f"Started/Resumed task: {task_name}")
        except Exception as e:
            self.logger.error(f"Error starting/resuming task: {e}")

    def handle_pause(self):
        try:
            if self.current_task_id:
                duration = pause_task(self.current_task_id)
                self.widget.update_button_states(task_active=False, task_paused=True)
                self.widget.pause_timer()  # Pause the timer
                self.logger.info(f"Task paused. Duration: {duration:.2f} hours")
        except Exception as e:
            self.logger.error(f"Error pausing task: {e}")

    def handle_stop(self):
        try:
            if self.current_task_id:
                total_duration = stop_task(self.current_task_id)
                self.current_task_id = None
                self.widget.set_task_name("No active task")
                self.widget.update_button_states(task_active=False)
                self.widget.stop_timer()  # Stop and reset the timer
                self.logger.info(
                    f"Task stopped. Total duration: {total_duration:.2f} hours"
                )
        except Exception as e:
            self.logger.error(f"Error stopping task: {e}")

    def handle_expand(self):
        """Handle expand button click"""
        try:
            self.widget.handle_expand()
        except Exception as e:
            self.logger.error(f"Error opening main window: {e}")

    def cleanup(self):
        """Clean up resources before quitting"""
        self.is_quitting = True
        if self.widget:
            if self.widget.main_window:
                self.widget.main_window.close()
            self.widget.close()
        if self.tray_icon:
            self.tray_icon.hide()

    def handle_quit(self):
        """Handle quit action from tray menu"""
        self.is_quitting = True
        self.app.quit()

    def run(self):
        # Initialize database
        init_db()

        # Show the widget
        self.widget.show()

        # Start the application
        return self.app.exec()


def main():
    app = TimeTrackerApp()
    sys.exit(app.run())


if __name__ == "__main__":
    main()
