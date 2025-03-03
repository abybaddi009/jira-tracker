import time

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from notification import NotificationManager


class TimerReminderTracker(QObject):
    """
    Tracks if the user is not recording any time and sends periodic reminders.
    Reminds users every 5 minutes if they are not tracking time.
    """

    reminder_triggered = pyqtSignal()  # Signal emitted when reminder is sent

    def __init__(self, parent=None, reminder_interval=60):  # 300 seconds = 5 minutes
        super().__init__(parent)
        self.notification_manager = NotificationManager()
        self.reminder_interval = reminder_interval
        self.is_running = False
        self.timer_widget = parent

        # Setup timer for periodic reminder checks
        self.reminder_timer = QTimer(self)
        self.reminder_timer.timeout.connect(self.check_timer_status)

    def start(self):
        """Start the reminder tracker"""
        self.is_running = True
        self.reminder_timer.start(self.reminder_interval * 1000)  # Convert to ms

    def stop(self):
        """Stop the reminder tracker"""
        self.is_running = False
        self.reminder_timer.stop()

    def check_timer_status(self):
        """Check if user has an active timer and send reminder if not"""
        if not self.is_running:
            return

        # Check if the timer in the parent widget is active
        if (
            hasattr(self.timer_widget, "update_timer")
            and not self.timer_widget.update_timer.isActive()
        ):
            self.send_reminder()

    def send_reminder(self):
        """Send a reminder notification to the user"""
        self.notification_manager.send_notification(
            "Time Tracking Reminder",
            "You're not tracking any activity. Don't forget to log your time!",
            timeout=10000,
            priority="high",
        )
        self.reminder_triggered.emit()
