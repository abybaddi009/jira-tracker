import logging

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtGui import QFont, QColor, QBrush
from PyQt6.QtWidgets import (
    QCheckBox,
    QDateEdit,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMenu,
    QMenuBar,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from alchemy import (
    Task,
    delete_tasks,
    get_db_connection,
    get_tasks_for_date,
    update_task,
)
from jira_integration import JiraCredentialsDialog, log_work_to_jira
from time_tracking import calculate_duration
from utils import format_duration


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.selected_tasks = set()
        self.logger = logging.getLogger(__name__)
        self.edited_cells = set()  # Track edited cells
        self.HIGHLIGHT_COLOR = QColor(217, 237, 255)  # Light blue color
        self.loaded_tasks = []  # Store loaded tasks for comparison

        # Track if we're really quitting
        self.is_quitting = False

        self.table_headers = [
            {"name": "", "attr": None},  # Checkbox column
            {"name": "Task Name", "attr": "task_name"},
            {"name": "Start Time", "attr": "start_time"},
            {"name": "End Time", "attr": "end_time"},
            {"name": "Duration (hrs)", "attr": "duration"},
            {"name": "JIRA Key", "attr": "jira_key"},
            {"name": "Synced", "attr": "synced"},
            {"name": "Worklog ID", "attr": "worklog_id"},
        ]

        self.create_menu_bar()
        self.initUI()
        self.load_tasks_for_date()

    def create_menu_bar(self):
        """Create the menu bar with File menu"""
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")

        # Add JIRA Settings action
        jira_settings_action = file_menu.addAction("JIRA Settings")
        jira_settings_action.triggered.connect(self.show_jira_settings)

        # Add separator
        file_menu.addSeparator()

        # Add Exit action
        exit_action = file_menu.addAction("Exit")
        exit_action.triggered.connect(self.confirm_exit)

    def show_jira_settings(self):
        """Show the JIRA credentials dialog"""
        dialog = JiraCredentialsDialog(self)
        dialog.exec()

    def confirm_exit(self):
        """Show confirmation dialog before exiting"""
        reply = QMessageBox.question(
            self,
            "Confirm Exit",
            "Do you want to stop tracker and close?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.is_quitting = True  # Set flag to allow actual closing
            self.close()

    def initUI(self):
        self.setWindowTitle("Time Tracker - Daily Records")
        self.setMinimumSize(800, 400)

        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Create top controls layout
        top_controls = QHBoxLayout()

        # Add total hours label on the left
        self.total_hours_label = QLabel("Total Hours: 0.00")
        self.total_hours_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        top_controls.addWidget(self.total_hours_label)

        # Add stretch to push other controls to the right
        top_controls.addStretch()

        # Add date selector
        self.date_selector = QDateEdit()
        self.date_selector.setCalendarPopup(True)  # Allows calendar popup
        self.date_selector.setDate(QDate.currentDate())
        top_controls.addWidget(self.date_selector)

        # Add apply button
        self.apply_button = QPushButton("Apply")
        self.apply_button.clicked.connect(self.load_tasks_for_date)
        top_controls.addWidget(self.apply_button)

        # Add top controls to main layout
        layout.addLayout(top_controls)

        # Create table
        self.table = QTableWidget()
        self.table.setColumnCount(len(self.table_headers))
        self.table.setHorizontalHeaderLabels([h["name"] for h in self.table_headers])

        # Update header resize modes
        header = self.table.horizontalHeader()
        sample_checkbox = QCheckBox()
        checkbox_width = sample_checkbox.sizeHint().width()

        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(0, checkbox_width + 4)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        for i in range(2, len(self.table_headers) - 1):  # Adjust range for new column
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)

        self.table.setEditTriggers(
            QTableWidget.EditTrigger.DoubleClicked
            | QTableWidget.EditTrigger.EditKeyPressed
        )

        # Create bottom buttons
        button_layout = QHBoxLayout()
        self.sync_button = QPushButton("Sync Selected to JIRA")
        self.sync_button.clicked.connect(self.sync_selected_tasks)
        self.sync_button.setShortcut("Ctrl+J")
        self.sync_button.setToolTip("Sync selected tasks to JIRA (Ctrl+J)")
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.load_tasks_for_date)
        self.refresh_button.setShortcut("Ctrl+R")
        self.refresh_button.setToolTip("Refresh table (Ctrl+R)")
        self.recalculate_button = QPushButton("Recalculate Duration")
        self.recalculate_button.clicked.connect(self.recalculate_selected_durations)
        self.recalculate_button.setShortcut("Ctrl+D")
        self.recalculate_button.setToolTip("Recalculate duration for selected tasks (Ctrl+D)")
        self.delete_button = QPushButton("Delete Selected")
        self.delete_button.clicked.connect(self.delete_selected_tasks)
        self.delete_button.setVisible(False)
        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self.save_all_changes)
        self.save_button.setShortcut("Ctrl+S")
        self.save_button.setToolTip("Save all changes (Ctrl+S)")

        button_layout.addWidget(self.sync_button)
        button_layout.addWidget(self.refresh_button)
        button_layout.addWidget(self.recalculate_button)
        button_layout.addWidget(self.delete_button)
        button_layout.addWidget(self.save_button)
        button_layout.addStretch()

        # Add widgets to layout
        layout.addWidget(self.table)
        layout.addLayout(button_layout)

    # Add new method to handle duration recalculation
    def recalculate_selected_durations(self):
        """Recalculate and update durations for selected tasks"""
        try:
            if not self.selected_tasks:
                QMessageBox.information(
                    self, "Info", "Please select tasks to recalculate"
                )
                return

            for row in range(self.table.rowCount()):
                task_id = self.table.item(row, 1).data(Qt.ItemDataRole.UserRole)
                if task_id in self.selected_tasks:
                    start_time = self.table.item(row, 2).text()
                    end_time = self.table.item(row, 3).text()

                    new_duration = calculate_duration(start_time, end_time)
                    duration_item = self.table.item(row, 4)
                    
                    # Update the duration display with formatted text
                    duration_item.setText(format_duration(new_duration))
                    # Store the raw duration value for calculations
                    duration_item.setData(Qt.ItemDataRole.UserRole, new_duration)

                    # Update the duration in the database
                    update_task(task_id, duration=new_duration)

            # Update the total hours label
            self.update_total_hours_label()

            QMessageBox.information(
                self, "Success", "Durations recalculated successfully"
            )

        except Exception as e:
            self.logger.error(f"Error recalculating durations: {e}")
            QMessageBox.critical(
                self, "Error", f"Failed to recalculate durations: {str(e)}"
            )

    def load_tasks_for_date(self):
        """Load tasks for the selected date"""
        try:
            selected_date = self.date_selector.date().toPyDate()
            tasks = get_tasks_for_date(selected_date)
            self.populate_table(tasks)
            # Update the total hours label
            self.update_total_hours_label()
        except Exception as e:
            self.logger.error(f"Error loading tasks for date: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load tasks: {str(e)}")

    def populate_table(self, tasks):
        """Populate table with tasks and store them for comparison"""
        self.loaded_tasks = tasks  # Store tasks for later comparison
        self.edited_cells.clear()
        self.table.setRowCount(len(tasks))

        # Safely disconnect the itemChanged signal if it's connected
        try:
            self.table.itemChanged.disconnect(self.on_item_changed)
        except TypeError:  # Signal was not connected
            pass

        for row, task in enumerate(tasks):
            for col, header in enumerate(self.table_headers):
                if header["attr"] is None:
                    container = QWidget()
                    layout = QHBoxLayout(container)
                    layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    layout.setContentsMargins(0, 0, 0, 0)
                    checkbox = QCheckBox()
                    if task.task_id in self.selected_tasks:
                        checkbox.setCheckState(Qt.CheckState.Checked)
                    checkbox.stateChanged.connect(self.on_checkbox_changed)
                    layout.addWidget(checkbox)
                    self.table.setCellWidget(row, col, container)
                else:
                    value = getattr(task, header["attr"])
                    if header["attr"] == "task_name":
                        item = QTableWidgetItem(value)
                        item.setData(Qt.ItemDataRole.UserRole, task.task_id)
                    elif header["attr"] == "duration" and value is not None:
                        formatted_duration = format_duration(value)
                        item = QTableWidgetItem(formatted_duration)
                        # Store the raw duration value for calculations
                        item.setData(Qt.ItemDataRole.UserRole, value)
                        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    elif header["attr"] == "synced":
                        item = QTableWidgetItem("Yes" if value else "No")
                        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    elif header["attr"] == "worklog_id":
                        item = QTableWidgetItem(str(value or ""))
                        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    else:
                        item = QTableWidgetItem(str(value or ""))
                    self.table.setItem(row, col, item)

        # Connect the itemChanged signal
        self.table.itemChanged.connect(self.on_item_changed)

    def update_total_hours_label(self):
        """Calculate and update the total hours label from current tasks"""
        total_hours = 0.0
        for row in range(self.table.rowCount()):
            duration_item = self.table.item(row, 4)
            if duration_item:
                # Get the raw duration value stored in UserRole
                duration = duration_item.data(Qt.ItemDataRole.UserRole)
                if duration is not None:
                    total_hours += duration

        formatted_total = format_duration(total_hours)
        self.total_hours_label.setText(f"Total Hours: {formatted_total}")

    def on_checkbox_changed(self, state):
        checkbox = self.sender()
        row = self.get_checkbox_row(checkbox)
        task_id = self.table.item(row, 1).data(Qt.ItemDataRole.UserRole)

        if state == Qt.CheckState.Checked.value:
            self.selected_tasks.add(task_id)
        else:
            self.selected_tasks.discard(task_id)

        self.delete_button.setVisible(len(self.selected_tasks) > 0)

    def get_checkbox_row(self, checkbox):
        for row in range(self.table.rowCount()):
            container = self.table.cellWidget(row, 0)
            if container and checkbox in container.children():
                return row
        return -1

    def on_item_changed(self, item):
        """Handle when a cell is edited by the user"""
        if not item:
            return

        row = item.row()
        col = item.column()
        
        # Don't track changes for certain columns
        header_attr = self.table_headers[col]["attr"]
        if header_attr in ["duration", "synced", "worklog_id"] or header_attr is None:
            return

        # Get the original value from loaded_tasks
        task = self.loaded_tasks[row]
        original_value = str(getattr(task, header_attr) or "")
        current_value = item.text()

        # Compare and highlight if different
        if original_value != current_value:
            cell_id = (row, col)
            self.edited_cells.add(cell_id)
            item.setBackground(QBrush(self.HIGHLIGHT_COLOR))
        else:
            cell_id = (row, col)
            if cell_id in self.edited_cells:
                self.edited_cells.remove(cell_id)
            item.setBackground(QBrush())

    def save_all_changes(self):
        """Save all modified rows to the database"""
        try:
            updates = []
            for row in range(self.table.rowCount()):
                task_id = self.table.item(row, 1).data(Qt.ItemDataRole.UserRole)
                duration_item = self.table.item(row, 4)
                duration = duration_item.data(Qt.ItemDataRole.UserRole) if duration_item else 0
                
                update_data = {
                    "task_name": self.table.item(row, 1).text(),
                    "start_time": self.table.item(row, 2).text(),
                    "end_time": self.table.item(row, 3).text(),
                    "duration": duration,
                    "jira_key": self.table.item(row, 5).text(),
                }
                updates.append((task_id, update_data))

            # Temporarily disconnect the itemChanged signal
            self.table.itemChanged.disconnect(self.on_item_changed)

            # Clear highlights from edited cells
            for row, col in self.edited_cells:
                item = self.table.item(row, col)
                if item:
                    item.setBackground(QBrush())

            self.edited_cells.clear()

            for task_id, update_data in updates:
                update_task(task_id, **update_data)

            # Update the total hours label
            self.update_total_hours_label()

            # Reconnect the itemChanged signal
            self.table.itemChanged.connect(self.on_item_changed)

            QMessageBox.information(self, "Success", "All changes saved successfully")
        except Exception as e:
            self.logger.error(f"Error saving changes: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save changes: {str(e)}")

    def delete_selected_tasks(self):
        if not self.selected_tasks:
            return

        reply = QMessageBox.question(
            self,
            "Confirm Deletion",
            "Are you sure you want to delete the selected tasks?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                delete_tasks(list(self.selected_tasks))
                self.selected_tasks.clear()
                self.delete_button.setVisible(False)
                self.load_tasks_for_date()
                self.update_total_hours_label()
                QMessageBox.information(self, "Success", "Tasks deleted successfully")
            except Exception as e:
                self.logger.error(f"Error deleting tasks: {e}")
                QMessageBox.critical(self, "Error", f"Failed to delete tasks: {str(e)}")

    def sync_selected_tasks(self):
        """Sync selected tasks to JIRA"""
        try:
            if not self.selected_tasks:
                QMessageBox.information(self, "Info", "Please select tasks to sync")
                return

            session = get_db_connection()
            tasks = (
                session.query(Task).filter(Task.task_id.in_(self.selected_tasks)).all()
            )

            # Create and configure progress dialog
            progress = QProgressDialog(
                "Syncing tasks to JIRA...", "Cancel", 0, len(tasks), self
            )
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setWindowTitle("Sync Progress")
            progress.setMinimumDuration(0)  # Show immediately

            for i, task in enumerate(tasks):
                if progress.wasCanceled():
                    break

                if task.synced:
                    progress.setValue(i + 1)
                    continue

                jira_key = task.jira_key
                duration = task.duration or 0

                if not jira_key:
                    progress.close()  # Temporarily hide progress for input dialog
                    jira_key, ok = QInputDialog.getText(
                        self, "Enter JIRA Key", "JIRA Key:"
                    )
                    if ok:
                        task.jira_key = jira_key
                        session.commit()
                    progress.show()  # Show progress again
                    progress.setValue(i + 1)
                    continue

                if duration > 0:
                    log_work_to_jira(task.task_id, duration, jira_key)

                progress.setValue(i + 1)

            progress.close()
            session.close()
            self.load_tasks_for_date()  # Refresh the table
            QMessageBox.information(self, "Success", "Selected tasks synced to JIRA")

        except Exception as e:
            self.logger.error(f"Error syncing to JIRA: {e}")
            QMessageBox.critical(self, "Error", f"Failed to sync to JIRA: {str(e)}")

    def closeEvent(self, event):
        """Handle window close event"""
        if self.is_quitting:
            # If we're actually quitting the app, accept the close event
            event.accept()
        else:
            # Otherwise just hide the window
            event.ignore()
            self.hide()
