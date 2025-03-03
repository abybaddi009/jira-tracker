import logging
import os
import platform
from datetime import timedelta

from plyer import notification

# Add imports for sound
if platform.system() == "Windows":
    import winsound
elif platform.system() in ["Darwin", "Linux"]:
    from subprocess import call

    # Add specific import for DBus notifications (for KDE)
    try:
        import dbus

        DBUS_AVAILABLE = True
    except ImportError:
        DBUS_AVAILABLE = False

# Configure logger
logger = logging.getLogger(__name__)


class NotificationManager:
    """
    Cross-platform notification manager for time tracking notifications.
    Uses plyer for platform-independent desktop notifications.
    """

    def __init__(self, app_name="Time Tracker"):
        """Initialize notification manager with application name"""
        self.app_name = app_name
        self.system = platform.system()
        self.enabled = True
        self.sound_enabled = True
        # Track notification times to prevent spam
        self.last_sent = {}
        self.widget = None  # Reference to the TimeTrackerWidget
        logger.info(f"Notification system initialized for {self.system}")

    def toggle_notifications(self, enabled=None):
        """Enable or disable notifications"""
        if enabled is not None:
            self.enabled = enabled
        else:
            self.enabled = not self.enabled
        return self.enabled

    def toggle_sound(self, enabled=None):
        """Enable or disable notification sounds"""
        if enabled is not None:
            self.sound_enabled = enabled
        else:
            self.sound_enabled = not self.sound_enabled
        return self.sound_enabled

    def play_sound(self, sound_type="default"):
        """
        Play a notification sound based on the platform

        Args:
            sound_type: Type of sound ("default", "warning", "error")
        """
        if not self.sound_enabled:
            return

        try:
            if self.system == "Windows":
                if sound_type == "warning":
                    winsound.PlaySound("SystemHand", winsound.SND_ALIAS)
                elif sound_type == "error":
                    winsound.PlaySound("SystemExclamation", winsound.SND_ALIAS)
                else:
                    winsound.PlaySound("SystemAsterisk", winsound.SND_ALIAS)

            elif self.system == "Darwin":  # macOS
                sound_name = "Ping" if sound_type == "default" else "Basso"
                os.system(f"afplay /System/Library/Sounds/{sound_name}.aiff")

            elif self.system == "Linux":
                # Use paplay if available (PulseAudio), otherwise fall back to aplay
                sound_file = "/usr/share/sounds/freedesktop/stereo/message.oga"
                if os.path.exists("/usr/bin/paplay"):
                    call(["paplay", sound_file])
                else:
                    call(["aplay", "-q", sound_file])

        except Exception as e:
            logger.error(f"Failed to play notification sound: {e}")

    def _send_windows_notification(self, title, message, timeout=10, priority="normal"):
        """
        Send a notification specifically for Windows using win10toast

        Args:
            title: Notification title
            message: Notification message
            timeout: How long the notification should remain visible (seconds)
            priority: Priority level ("low", "normal", "high")

        Returns:
            bool: True if the notification was sent successfully, False otherwise
        """
        try:
            from win10toast import ToastNotifier
            toaster = ToastNotifier()
            
            # Construct full title
            full_title = f"{self.app_name}: {title}"
            
            # Set icon based on priority
            icon_path = None
            if priority == "high":
                icon_path = "SystemHand"  # Windows error icon
            else:
                icon_path = "SystemAsterisk"  # Windows info icon

            # Show notification
            toaster.show_toast(
                full_title,
                message,
                icon_path=icon_path,
                duration=timeout,
                threaded=True  # Use threaded to prevent blocking
            )

            # Play sound based on priority
            sound_type = "warning" if priority == "high" else "default"
            self.play_sound(sound_type)

            logger.debug(f"Windows notification sent: {title}")
            return True

        except Exception as e:
            logger.warning(f"Failed to send Windows notification: {e}")
            return False

    def _send_kde_notification(self, title, message, timeout=10, priority="normal"):
        """
        Send a notification specifically for KDE desktop environment using DBus

        Args:
            title: Notification title
            message: Notification message
            timeout: How long the notification should remain visible (seconds)
            priority: Priority level ("low", "normal", "high")

        Returns:
            bool: True if the notification was sent successfully, False otherwise
        """
        if not DBUS_AVAILABLE:
            logger.debug("DBus not available, can't send KDE notification")
            return False

        try:
            # Convert timeout to milliseconds for DBus
            timeout_ms = timeout * 1000
            full_title = f"{self.app_name}: {title}"

            bus = dbus.SessionBus()
            notify_obj = bus.get_object(
                "org.freedesktop.Notifications", "/org/freedesktop/Notifications"
            )
            notify_interface = dbus.Interface(
                notify_obj, "org.freedesktop.Notifications"
            )

            # Set appropriate urgency based on priority
            hints = {}
            if priority == "high":
                hints = {"urgency": dbus.Byte(2)}
            elif priority == "low":
                hints = {"urgency": dbus.Byte(0)}
            else:
                hints = {"urgency": dbus.Byte(1)}

            # Send notification via DBus
            notify_interface.Notify(
                self.app_name,  # App name
                0,  # Replaces ID
                "",  # Icon (empty for default)
                full_title,  # Summary/title
                message,  # Body/message
                [],  # Actions
                hints,  # Hints including urgency
                timeout_ms,  # Timeout in ms
            )

            # Play sound based on priority
            sound_type = "warning" if priority == "high" else "default"
            self.play_sound(sound_type)

            logger.debug(f"KDE notification sent via DBus: {title}")
            return True
        except Exception as e:
            logger.warning(f"Failed to send KDE notification via DBus: {e}")
            return False

    def _send_unity_notification(self, title, message, timeout=10, priority="normal"):
        """
        Send a notification specifically for Unity desktop environment

        Args:
            title: Notification title
            message: Notification message
            timeout: How long the notification should remain visible (seconds)
            priority: Priority level ("low", "normal", "high")

        Returns:
            bool: True if the notification was sent successfully, False otherwise
        """
        try:
            # Unity uses the notify-send command
            import subprocess

            full_title = f"{self.app_name}: {title}"

            # Map priority to urgency levels
            urgency = "normal"
            if priority == "high":
                urgency = "critical"
            elif priority == "low":
                urgency = "low"

            # Use notify-send command
            subprocess.run(
                [
                    "notify-send",
                    full_title,
                    message,
                    "-t",
                    str(int(timeout * 1000)),  # Convert to milliseconds
                    "-u",
                    urgency,
                ],
                check=True,
            )

            # Play sound based on priority
            sound_type = "warning" if priority == "high" else "default"
            self.play_sound(sound_type)

            logger.debug(f"Unity notification sent via notify-send: {title}")
            return True
        except Exception as e:
            logger.warning(f"Failed to send Unity notification: {e}")
            return False

    def set_widget(self, widget):
        """Set the reference to the TimeTrackerWidget"""
        self.widget = widget

    def send_notification(self, title, message, timeout=10, priority="normal"):
        """
        Send a desktop notification

        Args:
            title: Notification title
            message: Notification message
            timeout: How long the notification should remain visible (seconds)
            priority: Priority level ("low", "normal", "high")
        """
        if not self.enabled:
            return

        try:
            # Detect desktop environment for Linux
            if self.system == "Linux":
                desktop_env = os.environ.get("XDG_CURRENT_DESKTOP", "").upper()

                # Try KDE-specific notification
                if desktop_env == "KDE":
                    if self._send_kde_notification(title, message, timeout, priority):
                        return

                # Try Unity-specific notification
                elif desktop_env in ["UNITY", "GNOME", "X-CINNAMON"]:
                    if self._send_unity_notification(title, message, timeout, priority):
                        return

            # Try Windows-specific notification
            if self.system == "Windows":
                if self._send_windows_notification(title, message, timeout, priority):
                    return

            # Fall back to plyer for other platforms or if specific implementations fail
            notification.notify(
                title=f"{self.app_name}: {title}",
                message=message,
                app_name=self.app_name,
                timeout=timeout,
            )

            # Play sound based on priority
            sound_type = "warning" if priority == "high" else "default"
            self.play_sound(sound_type)

            logger.debug(f"Notification sent via plyer: {title}")

            # Grab attention if widget is available and priority is high
            if self.widget and priority == "high":
                self.widget.grab_attention()

        except Exception as e:
            logger.error(f"Failed to send notification: {e}")

            # Last resort: print to console
            print(f"\n[{self.app_name}] {title}: {message}\n")

    def notify_timer_running(self, task_name, elapsed_time, jira_key=None):
        """
        Send notification about a running timer

        Args:
            task_name: Name of the active task
            elapsed_time: Time elapsed in seconds
            jira_key: Optional JIRA ticket key
        """
        # Format the elapsed time as hours:minutes:seconds
        hours, remainder = divmod(elapsed_time, 3600)
        minutes, seconds = divmod(remainder, 60)
        time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

        # Construct task identifier
        task_identifier = f"{task_name} ({jira_key})" if jira_key else task_name

        # Determine notification type based on elapsed time
        if hours >= 1:
            # High priority notification for timers running > 1 hour
            # Only send once per 30 minutes after the first hour
            notification_key = f"long_timer_{task_identifier}"
            last_time = self.last_sent.get(notification_key, 0)

            if elapsed_time - last_time >= 1800:  # 30 minutes in seconds
                title = "Timer Running for a Long Time"
                message = f"Task '{task_identifier}' has been running for {time_str}"
                self.send_notification(title, message, priority="high")
                self.last_sent[notification_key] = elapsed_time
        else:
            # Low priority periodic notification (every 15 minutes)
            notification_key = f"periodic_{task_identifier}"
            last_time = self.last_sent.get(notification_key, 0)

            if elapsed_time - last_time >= 900:  # 15 minutes in seconds
                title = "Timer Running"
                message = f"Task '{task_identifier}' has been running for {time_str}"
                self.send_notification(title, message, priority="low")
                self.last_sent[notification_key] = elapsed_time

    def notify_timer_completed(self, task_name, elapsed_time, jira_key=None):
        """
        Send notification when a timer is completed (stopped)

        Args:
            task_name: Name of the completed task
            elapsed_time: Total time in seconds
            jira_key: Optional JIRA ticket key
        """
        # Format the elapsed time
        time_delta = timedelta(seconds=elapsed_time)

        # Format hours and minutes
        hours = time_delta.seconds // 3600
        minutes = (time_delta.seconds % 3600) // 60

        # Create a readable time string
        if hours > 0:
            time_str = f"{hours} {'hour' if hours == 1 else 'hours'}"
            if minutes > 0:
                time_str += f" and {minutes} {'minute' if minutes == 1 else 'minutes'}"
        else:
            time_str = f"{minutes} {'minute' if minutes == 1 else 'minutes'}"

        task_identifier = f"{task_name} ({jira_key})" if jira_key else task_name

        title = "Timer Completed"
        message = f"You spent {time_str} on '{task_identifier}'"

        self.send_notification(title, message, priority="normal")
