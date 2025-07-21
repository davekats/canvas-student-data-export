# Introduction

The Canvas Student Data Export Tool exports nearly all of a student's data from the Instructure Canvas Learning Management System (Canvas LMS).  
This is useful when you are graduating or leaving your college or university, and would like to have a backup of all the data you had in canvas.

The tool exports the following data:
- Course Assignments (including submissions and attachments)
- Course Announcements
- Course Discussions
- Course Pages
- Course Files
- Course Modules
- (Optional) HTML snapshots of:
    - Course Home Page
    - Grades Page
    - Assignments
    - Announcements
    - Discussions
    - Modules

Data is saved in JSON (and optionally HTML) format and organized into folders by academic term and course.

Example output structure:
- Fall 2023
  - CS 101
    - announcements/
      - First Announcement/
        - announcement_1.html
      - announcement_list.html
    - assignments/
      - Sample Assignment/
        - assignment.html
        - submission.html
      - assignment_list.html
    - course files/
      - file_1.docx
      - file_2.png
    - discussions/
      - Sample Discussion
        - discussion_1.html
      - discussion_list.html
    - modules/
      - Sample Module
        - Sample Assignment.html
        - Sample Discussion.html
        - Sample Page.html
        - Sample Quiz.html
      - modules_list.html
    - grades.html
    - homepage.html
    - CS 101.json
  - ENGL 101
    - ...
- Spring 2024
  - ...
- all_output.json

# Getting Started

## Dependencies
- Python 3.8 or newer
- Node.js 16 or newer (only needed for HTML snapshots)

1.  **Install Python dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

2.  **(Optional) Install SingleFile for HTML snapshots:**
    This step requires Node.js.
    ```bash
    npm install
    ```

## Configuration

To use the tool, you must create a `credentials.yaml` file in the project root. You can also specify a different path using the `-c` or `--config` command-line option.

Create the `credentials.yaml` file with the following content:

```yaml
# The URL of your Canvas instance (e.g., https://your-school.instructure.com)
API_URL: https://example.instructure.com
# Your Canvas API token
API_KEY: <Your Canvas API token>
# Your Canvas User ID
USER_ID: 123456
# Path to your browser cookies file (Netscape format).
# This is only required when using the --singlefile flag.
COOKIES_PATH: ./cookies.txt
# (Optional) Path to your Chrome/Chromium executable if SingleFile cannot find it.
# CHROME_PATH: C:\Program Files\Google\Chrome\Application\chrome.exe
# (Optional) A list of course IDs to skip when exporting data.
# COURSES_TO_SKIP:
#   - 12345
#   - 67890
```

### Finding Your Credentials

-   **`API_URL`**: Your institution's Canvas URL.
-   **`API_KEY`**: In Canvas, go to `Account` > `Settings`, scroll down to `Approved Integrations`, and click `+ New Access Token`.
-   **`USER_ID`**: After logging into Canvas, visit `https://<your-canvas-url>/api/v1/users/self`. Your browser will show a JSON response; find the `id` field.
-   **`COOKIES_PATH`**: Required **only if** you use the `--singlefile` flag. To save complete HTML pages, you need your browser's cookies. Use a browser extension like "Get cookies.txt Clean" for Chrome to export them in Netscape format.
-   **`CHROME_PATH`** (Optional): The script attempts to auto-detect Chrome/Chromium on Windows, macOS, and Linux. If it fails, you can specify the path here.
-   **`COURSES_TO_SKIP`** (Optional): A list of course IDs to exclude from the export. To find a course ID, go to the course's homepage and look at the URL for the number that follows `/courses/`.

## Running the Exporter

Once your `credentials.yaml` is set up, run the script:

```bash
python export.py [options]
```

**Options:**

| Flag                   | Description                                             | Default            |
| ---------------------- | ------------------------------------------------------- | ------------------ |
| `-c`, `--config <path>`  | Path to your YAML credentials file.                     | `credentials.yaml` |
| `-o`, `--output <path>`  | Directory to store exported data.                       | `./output`         |
| `--singlefile`         | Enable HTML snapshot capture with SingleFile.           | Disabled           |
| `--version`            | Show the version of the tool and exit.                  | N/A                |

**Example:**

```bash
# Run with default settings (uses ./credentials.yaml, outputs to ./output)
python export.py

# Run with a custom output directory and enable HTML snapshots
python export.py -o /path/to/my-canvas-backup --singlefile
```

# Contribute

I would love to see this script's functionality expanded and improved! I welcome all pull requests :)  
Thank you!
