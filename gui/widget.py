import json

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from logging_setup import get_logger
from notification import NotificationManager
from reminder_tracker import TimerReminderTracker
from utils import resource_path

from .main_window import MainWindow

logger = get_logger(__name__)


class TimeTrackerWidget(QWidget):
    # Signals for button clicks
    start_clicked = pyqtSignal()
    pause_clicked = pyqtSignal()
    stop_clicked = pyqtSignal()
    expand_clicked = pyqtSignal()
    visibility_changed = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self.main_window = None
        self.blink_timer = QTimer()
        self.blink_timer.timeout.connect(self.toggle_time_visibility)
        self.blink_state = True
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_time)
        self.elapsed_time = 0

        self.notification_manager = NotificationManager()
        self.notification_manager.set_widget(self)
        self.notification_timer = QTimer()
        self.notification_timer.timeout.connect(self.check_notification_triggers)
        self.notification_timer.start(60000)  # Check for notifications every minute

        # Add reminder tracker
        self.reminder_tracker = TimerReminderTracker(self)
        self.reminder_tracker.start()  # Start immediately to check periodically

        self.initUI()

    def initUI(self):
        # Set window flags for always-on-top and frameless window
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint
        )
        self.setStyleSheet(
            """
            TimeTrackerWidget {
                background-color: #fff;
                border: 1px solid #808080;
                border-radius: 10px;
            }
        """
        )

        # Main layout
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)

        # Top bar layout
        top_bar = QHBoxLayout()

        # Add JIRA tracker label
        jira_label = QLabel("JIRA Time tracker")
        jira_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        top_bar.addWidget(jira_label)

        # Add spacer to push buttons to the right
        top_bar.addStretch()

        # Create minimize and close buttons for top bar
        self.window_minimize_button = QPushButton()
        self.window_minimize_button.setIcon(QIcon(resource_path("static/minimize.png")))
        self.window_minimize_button.setToolTip("Minimize")
        self.window_minimize_button.clicked.connect(self.showMinimized)
        self.window_minimize_button.setFixedSize(24, 24)

        self.close_button = QPushButton()
        self.close_button.setIcon(QIcon(resource_path("static/close.png")))
        self.close_button.setToolTip("Close")
        self.close_button.clicked.connect(self.close)
        self.close_button.setFixedSize(24, 24)

        top_bar.addWidget(self.window_minimize_button)
        top_bar.addWidget(self.close_button)

        layout.addLayout(top_bar)

        # Add horizontal divider
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(divider)

        # Task selection dropdown
        self.task_dropdown = QComboBox()
        self.task_dropdown.addItems(self.load_tasks())
        self.task_dropdown.setCurrentText("Select a task")
        self.task_dropdown.setFont(QFont("Arial", 10))
        layout.addWidget(self.task_dropdown)

        # Task and time layout
        task_time_layout = QVBoxLayout()

        # Task name label
        self.task_label = QLabel("No active task")
        self.task_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        self.task_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.task_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        task_time_layout.addWidget(self.task_label)

        # JIRA ticket textbox
        self.jira_ticket = QLineEdit()
        self.jira_ticket.setPlaceholderText("Enter JIRA ticket")
        self.jira_ticket.setFixedHeight(24)
        self.jira_ticket.setFont(QFont("Arial", 10))
        task_time_layout.addWidget(self.jira_ticket)

        # Time label
        self.time_label = QLabel("00:00:00")
        self.time_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        task_time_layout.addWidget(self.time_label)

        layout.addLayout(task_time_layout)

        # Buttons layout
        button_layout = QHBoxLayout()

        # Create control buttons with icons
        self.start_button = QPushButton()
        self.start_button.setIcon(QIcon(resource_path("static/start.png")))
        self.start_button.setToolTip("Start")

        self.pause_button = QPushButton()
        self.pause_button.setIcon(QIcon(resource_path("static/pause.png")))
        self.pause_button.setToolTip("Pause")

        self.stop_button = QPushButton()
        self.stop_button.setIcon(QIcon(resource_path("static/stop.png")))
        self.stop_button.setToolTip("Stop")

        self.expand_button = QPushButton()
        self.expand_button.setIcon(QIcon(resource_path("static/expand.png")))
        self.expand_button.setToolTip("Expand")

        # Connect buttons to signals
        self.start_button.clicked.connect(self.start_clicked.emit)
        self.pause_button.clicked.connect(self.pause_clicked.emit)
        self.stop_button.clicked.connect(self.stop_clicked.emit)
        self.expand_button.clicked.connect(self.expand_clicked.emit)
        self.jira_ticket.textChanged.connect(self.on_jira_ticket_changed)

        # Add buttons to layout
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.pause_button)
        button_layout.addWidget(self.stop_button)
        button_layout.addWidget(self.expand_button)

        layout.addLayout(button_layout)
        self.setLayout(layout)

        # Set initial button states
        self.start_button.setEnabled(False)
        self.pause_button.setEnabled(False)
        self.stop_button.setEnabled(False)

        # Set size and position
        self.resize(300, 100)
        self.move(100, 100)

    def check_notification_triggers(self):
        """Check if notifications should be triggered based on timer state"""
        if self.update_timer.isActive():
            # Timer is running, send appropriate notification
            task_name = self.task_label.text()
            jira_key = self.jira_ticket.text()
            self.notification_manager.notify_timer_running(
                task_name, self.elapsed_time, jira_key
            )

    def get_selected_task(self):
        """Return the currently selected task"""
        return self.task_dropdown.currentText()

    def get_task_and_ticket(self):
        """Returns the currently selected task and the ticket number"""
        return self.task_dropdown.currentText(), self.jira_ticket.text()

    def on_jira_ticket_changed(self, text):
        """Handle JIRA ticket text changes"""
        # Only update button states if timer is not running
        if not self.update_timer.isActive():
            self.update_button_states()

    def load_tasks(self):
        """Load tasks from tasks.json"""
        try:
            tasks_path = resource_path("tasks_new.json")
            with open(tasks_path, "r") as f:
                data = json.load(f)
                return data.get("tasks", [])
        except Exception as e:
            logger.error(f"Error loading tasks from {tasks_path}: {e}")
            return ["No tasks available"]

    def set_task_name(self, name):
        """Update the task name label and dropdown"""
        self.task_label.setText(name)
        index = self.task_dropdown.findText(name)
        if index >= 0:
            self.task_dropdown.setCurrentIndex(index)

    def update_button_states(self, task_active=False, task_paused=False):
        """Update button states based on whether a task is active"""
        # For paused tasks, allow start button to resume
        is_enabled = (
            (not task_active or task_paused)
            and hasattr(self, "jira_ticket")
            and self.jira_ticket.text() != ""
            and self.jira_ticket.text().startswith("WPM-")
            and len(self.jira_ticket.text()) > 5
        )
        self.start_button.setEnabled(is_enabled)
        self.pause_button.setEnabled(task_active and not task_paused)
        self.stop_button.setEnabled(task_active or task_paused)

        # Disable task selection and JIRA ticket input while timer is running
        self.task_dropdown.setEnabled(not task_active or task_paused)
        self.jira_ticket.setEnabled(not task_active or task_paused)

    def mousePressEvent(self, event):
        """Enable dragging the widget"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = (
                event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )
            event.accept()

    def mouseMoveEvent(self, event):
        """Handle widget dragging"""
        if event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    def handle_expand(self):
        """Open the main window when expand button is clicked"""
        if not self.main_window:
            self.main_window = MainWindow()
        self.main_window.show()
        self.main_window.raise_()
        self.main_window.activateWindow()

    def start_timer(self):
        """Start the timer updates"""
        self.elapsed_time = 0
        self.update_timer.start(1000)  # Update every 1000ms (1 second)
        self.reminder_tracker.stop()  # Stop reminders while timer is running
        # Disable task selection and JIRA ticket input
        self.task_dropdown.setEnabled(False)
        self.jira_ticket.setEnabled(False)

    def pause_timer(self):
        """Pause the timer updates"""
        self.update_timer.stop()
        self.reminder_tracker.start()  # Resume reminders when timer is paused

    def stop_timer(self):
        """Stop the timer and reset"""
        self.update_timer.stop()
        self.reminder_tracker.start()  # Resume reminders when timer is stopped

        # Re-enable task selection and JIRA ticket input
        self.task_dropdown.setEnabled(True)
        self.jira_ticket.setEnabled(True)

        # Only show notification if actual time was tracked
        if self.elapsed_time > 60:  # Only notify if more than a minute tracked
            task_name = self.task_dropdown.currentText()
            jira_key = self.jira_ticket.text()
            self.notification_manager.notify_timer_completed(
                task_name, self.elapsed_time, jira_key
            )

        self.elapsed_time = 0
        self.set_time("00:00:00")

    def set_time(self, time_str):
        """Update the time label"""
        self.time_label.setText(time_str)

    def update_time(self):
        """Update the displayed time based on elapsed seconds"""
        hours = self.elapsed_time // 3600
        minutes = (self.elapsed_time % 3600) // 60
        seconds = self.elapsed_time % 60
        time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        self.set_time(time_str)
        self.elapsed_time += 1

    def toggle_time_visibility(self):
        """Toggle time label visibility for blinking effect"""
        self.blink_state = not self.blink_state
        self.time_label.setVisible(self.blink_state)

    def start_blinking(self):
        """Start blinking the time label"""
        self.blink_timer.start(500)  # Blink every 500ms

    def stop_blinking(self):
        """Stop blinking the time label"""
        self.blink_timer.stop()
        self.blink_state = True

    def _handle_tray_activation(self, reason):
        """Handle tray icon activation"""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            if self.isVisible():
                self.hide()
            else:
                self.show()
                self.raise_()
                self.activateWindow()

    def showEvent(self, event):
        """Override showEvent to emit our custom signal"""
        super().showEvent(event)
        self.visibility_changed.emit(True)

    def hideEvent(self, event):
        """Override hideEvent to emit our custom signal"""
        super().hideEvent(event)
        self.visibility_changed.emit(False)

    def closeEvent(self, event):
        """Handle widget close event"""
        if self.main_window:
            self.main_window.close()
        event.accept()
