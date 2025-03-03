import json
import os
from datetime import datetime

import environs
import requests
from environs import Env
from PyQt6.QtWidgets import (
    QDialog,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from alchemy import get_task, update_task
from logging_setup import get_logger
from utils import resource_path

logger = get_logger(__name__)

# Load environment variables


class JiraConfig:
    def __init__(self):
        env = environs.Env()
        env_path = resource_path(".env")
        env.read_env(env_path)

        self.domain = env.str("JIRA_DOMAIN")
        self.email = env.str("JIRA_EMAIL")
        self.api_token = env.str("JIRA_API_TOKEN")

        if not all([self.domain, self.email, self.api_token]):
            raise ValueError("Missing JIRA credentials in .env file")

        self.auth = (self.email, self.api_token)
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }


def log_work_to_jira(task_id, time_spent_hours, jira_key):
    """
    Log work to JIRA and store the worklog ID

    Args:
        task_id: Local task ID
        time_spent_hours: Time spent in hours
        jira_key: JIRA issue key (e.g., 'PROJ-123')
    """
    try:
        config = JiraConfig()
        task = get_task(task_id)

        if not task:
            raise ValueError(f"Task {task_id} not found")

        # Convert hours to seconds
        time_spent_seconds = int(time_spent_hours * 3600)

        # Convert the start_date to the user's system timezone
        start_time = datetime.fromisoformat(task[2])
        start_time = start_time.astimezone()

        # Prepare the worklog payload
        payload = {
            "comment": {
                "content": [
                    {
                        "content": [
                            {"text": task[1], "type": "text"}  # task name as comment
                        ],
                        "type": "paragraph",
                    }
                ],
                "type": "doc",
                "version": 1,
            },
            "started": start_time.strftime("%Y-%m-%dT%H:%M:%S.000%z"),
            "timeSpentSeconds": time_spent_seconds,
        }

        # Make the API request
        url = f"https://{config.domain}/rest/api/3/issue/{jira_key}/worklog"
        response = requests.post(
            url, data=json.dumps(payload), headers=config.headers, auth=config.auth
        )

        if response.status_code != 201:
            raise Exception(f"Failed to log work: {response.text}")

        # Get the worklog ID from response
        worklog_data = response.json()
        worklog_id = worklog_data["id"]

        # Store worklog ID in database
        update_task(task_id, worklog_id=worklog_id, synced=1)

        logger.info(f"Successfully logged work to JIRA issue {jira_key}")
        return worklog_id

    except Exception as e:
        logger.error(f"Error logging work to JIRA: {e}")
        raise


class JiraCredentialsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("JIRA Credentials")
        self.resize(400, 200)
        logger.info("Initializing JIRA Credentials Dialog")

        # Create form layout
        form_layout = QFormLayout()

        # Create input fields
        self.base_url_input = QLineEdit()
        self.username_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)

        # Add fields to form layout
        form_layout.addRow("JIRA Base URL:", self.base_url_input)
        form_layout.addRow("Username:", self.username_input)
        form_layout.addRow("API Token/Password:", self.password_input)

        # Create save button
        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self.save_credentials)

        # Create cancel button
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)

        # Create button layout
        button_layout = QVBoxLayout()
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.cancel_button)

        # Create main layout
        main_layout = QVBoxLayout()
        main_layout.addLayout(form_layout)
        main_layout.addLayout(button_layout)

        self.setLayout(main_layout)

        # First try to load existing credentials
        self.load_credentials()

        # If no credentials were loaded, try loading defaults from .env.example
        if not self.base_url_input.text():
            self.load_defaults_from_example()

    def load_credentials(self):
        """Load credentials from .env file if it exists"""
        try:
            env_path = resource_path(".env")
            logger.info(f"Attempting to load credentials from: {env_path}")
            logger.info(f"File exists: {os.path.exists(env_path)}")

            if os.path.exists(env_path):
                env = environs.Env()
                env.read_env(env_path)

                self.base_url_input.setText(env.str("JIRA_DOMAIN", ""))
                self.username_input.setText(env.str("JIRA_EMAIL", ""))
                self.password_input.setText(env.str("JIRA_API_TOKEN", ""))
                logger.info(
                    f"Successfully loaded JIRA credentials from {env_path}: "
                    f"domain={env.str('JIRA_DOMAIN', '')}, email={env.str('JIRA_EMAIL', '')}"
                )
            else:
                logger.warning(f"No .env file found at {env_path}")
        except Exception as e:
            logger.error(f"Error loading JIRA credentials: {e}", exc_info=True)

    def save_credentials(self):
        """Save credentials to .env file"""
        try:
            domain = self.base_url_input.text().strip()
            email = self.username_input.text().strip()
            api_token = self.password_input.text().strip()

            if not all([domain, email, api_token]):
                logger.warning("Attempted to save with missing fields")
                return

            env_path = resource_path(".env")
            logger.info(f"Attempting to save credentials to: {env_path}")

            env = environs.Env()
            if os.path.exists(env_path):
                logger.info(f"Existing .env file found at {env_path}")
                env.read_env(env_path)

            # Write to .env file
            logger.info(f"Writing new credentials to {env_path}")
            with open(env_path, "w") as f:
                f.write(f"JIRA_DOMAIN={domain}\n")
                f.write(f"JIRA_EMAIL={email}\n")
                f.write(f"JIRA_API_TOKEN={api_token}\n")

            logger.info(f"Successfully saved JIRA credentials to {env_path}")
            self.accept()
        except Exception as e:
            logger.error(f"Error saving JIRA credentials: {e}", exc_info=True)

    def get_credentials(self):
        return {
            "domain": self.base_url_input.text().strip(),
            "email": self.username_input.text().strip(),
            "token": self.password_input.text().strip(),
        }

    def load_defaults_from_example(self):
        """Load default values from .env.example"""
        try:
            env_example_path = resource_path(".env.example")
            logger.info(f"Loading defaults from .env.example at: {env_example_path}")

            if os.path.exists(env_example_path):
                env = environs.Env()
                env.read_env(env_example_path)

                # Only set values if they're empty
                if not self.base_url_input.text():
                    default_domain = env.str(
                        "JIRA_DOMAIN", "laborsolutions-tech.atlassian.net"
                    )
                    self.base_url_input.setText(default_domain)
                    logger.info(f"Loaded default domain: {default_domain}")

                if not self.username_input.text():
                    default_email = env.str("JIRA_EMAIL", "")
                    self.username_input.setText(default_email)
                    logger.info(f"Loaded default email: {default_email}")
            else:
                logger.warning("No .env.example file found for loading defaults")
        except Exception as e:
            logger.error(
                f"Error loading defaults from .env.example: {e}", exc_info=True
            )


def setup_jira_credentials():
    """
    Check if .env file exists and contains JIRA credentials.
    If not, prompt user for credentials using a settings dialog.
    """
    env = Env()
    env_path = resource_path(".env")
    logger.info(f"Setting up JIRA credentials. Looking for .env at: {env_path}")
    logger.info(f"Current working directory: {os.getcwd()}")
    logger.info(f"Absolute .env path: {os.path.abspath(env_path)}")

    file_exists = os.path.exists(env_path)
    logger.info(f".env file exists: {file_exists}")

    if not file_exists:
        logger.info("Checking if environment variables are set directly")
        # Check if variables are set in environment
        env_vars = {
            "JIRA_DOMAIN": os.environ.get("JIRA_DOMAIN"),
            "JIRA_EMAIL": os.environ.get("JIRA_EMAIL"),
            "JIRA_API_TOKEN": os.environ.get("JIRA_API_TOKEN"),
        }
        logger.info(
            f"Environment variables present: {[k for k, v in env_vars.items() if v]}"
        )

    try:
        if file_exists:
            logger.info("Reading from .env file")
            env.read_env(env_path)
        else:
            logger.info("Reading from environment variables")

        # Try to get all required variables
        domain = env("JIRA_DOMAIN")
        email = env("JIRA_EMAIL")
        token = env("JIRA_API_TOKEN")

        logger.info(f"Found credentials - Domain: {domain}, Email: {email}")

        # If we got here with no file, let's create one
        if not file_exists:
            logger.info("Creating .env file from environment variables")
            try:
                with open(env_path, "w") as f:
                    f.write(f"JIRA_DOMAIN={domain}\n")
                    f.write(f"JIRA_EMAIL={email}\n")
                    f.write(f"JIRA_API_TOKEN={token}\n")
                logger.info(f"Successfully created .env file at {env_path}")
            except Exception as e:
                logger.error(f"Failed to create .env file: {e}", exc_info=True)

        return True

    except Exception as e:
        logger.warning(f"Failed to load credentials: {e}", exc_info=True)

        # If any variable is missing, show the settings dialog
        default_domain = ""

        # Try to get default domain from .env.example
        env_example_path = resource_path(".env.example")
        logger.info(f"Looking for .env.example at: {env_example_path}")
        logger.info(f".env.example exists: {os.path.exists(env_example_path)}")

        if os.path.exists(env_example_path):
            try:
                env.read_env(env_example_path)
                default_domain = env.str(
                    "JIRA_DOMAIN", "laborsolutions-tech.atlassian.net"
                )
                logger.info(
                    f"Loaded default domain from .env.example: {default_domain}"
                )
            except Exception as e:
                logger.error(f"Error reading .env.example: {e}", exc_info=True)

        dialog = JiraCredentialsDialog()
        if dialog.exec():
            credentials = dialog.get_credentials()
            logger.info("Credentials dialog completed successfully")

            # Validate that all fields are filled
            if not all(credentials.values()):
                logger.warning("Not all credential fields were filled")
                QMessageBox.warning(None, "Error", "All fields are required!")
                return False

            try:
                # Write credentials to .env file
                env_path = resource_path(".env")
                logger.info(f"Writing new credentials to: {env_path}")
                with open(env_path, "w") as f:
                    f.write(f'JIRA_DOMAIN={credentials["domain"]}\n')
                    f.write(f'JIRA_EMAIL={credentials["email"]}\n')
                    f.write(f'JIRA_API_TOKEN={credentials["token"]}\n')
                logger.info(f"Successfully wrote credentials to {env_path}")

                # Read the new .env file
                env.read_env(env_path)
                return True
            except Exception as e:
                logger.error(f"Error saving credentials: {e}", exc_info=True)
                return False

        logger.info("User cancelled credentials dialog")
        return False
