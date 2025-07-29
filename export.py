# built in
import json
import os
import itertools
import re
import string
import argparse
import sys

# external
from bs4 import BeautifulSoup
from canvasapi import Canvas
from canvasapi.exceptions import ResourceDoesNotExist, Unauthorized, Forbidden, InvalidAccessToken, CanvasException
from singlefile import download_page, override_chrome_path
import dateutil.parser
import jsonpickle
import requests
import yaml

# Canvas API Error Handling Utility
class CanvasErrorHandler:
    @staticmethod
    def handle_canvas_exception(e, operation_description="operation"):
        """
        Handle Canvas API exceptions with appropriate messaging and classification.
        Returns (error_type, message)
        """
        if isinstance(e, InvalidAccessToken):
            return "authentication", f"Invalid Canvas API token. Please check your credentials.yaml file."
        
        elif isinstance(e, Unauthorized):
            # Check if this is a known student limitation
            if "submissions" in operation_description.lower():
                return "student_limitation", f"Not authorized to download every student's assignment submission. This is normal for student accounts."
            elif "file" in operation_description.lower():
                return "student_limitation", f"Not authorized to download some course files. This is normal for student accounts."
            else:
                return "authorization", f"Not authorized to perform {operation_description}. Check your Canvas permissions."
        
        elif isinstance(e, Forbidden):
            return "student_limitation", f"Access forbidden for {operation_description}. This may be normal for student accounts."
        
        elif isinstance(e, ResourceDoesNotExist):
            return "not_found", f"Resource not found for {operation_description}. It may have been deleted or moved."
        
        elif isinstance(e, CanvasException):
            return "canvas_error", f"Canvas API error during {operation_description}: {str(e)}"
        
        else:
            return "unknown_error", f"Unexpected error during {operation_description}: {str(e)}"
    
    @staticmethod
    def log_error(error_type, message, show_details=True, verbose=False):
        """Log error messages with appropriate formatting"""
        if error_type == "student_limitation":
            if show_details:
                print(f"    Note: {message}")
        elif error_type == "not_found":
            print(f"    Skipping: {message}")
        elif error_type in ["authentication", "authorization", "canvas_error", "unknown_error"]:
            print(f"    ERROR: {message}")
            if verbose:
                import traceback
                traceback.print_exc()
        else:
            print(f"    {message}")
            
    @staticmethod
    def is_fatal_error(error_type):
        """Check if an error type should stop execution"""
        return error_type in ["authentication", "canvas_error", "authorization"]

# Add counters for tracking successful extractions
class ExtractionStats:
    def __init__(self):
        self.assignments_found = 0
        self.submissions_found = 0
        self.announcements_found = 0
        self.discussions_found = 0
        self.pages_found = 0
        self.modules_found = 0
        self.module_items_found = 0
        self.files_downloaded = 0
        self.attachments_downloaded = 0
        self.html_pages_downloaded = 0
        self.json_files_created = 0
        self.student_limitation_warnings = 0
        self.error_count = 0
        
    def summary(self, dl_location, singlefile_enabled=False):
        summary_text = f"""
Data Extraction Summary:
  • {self.assignments_found} assignments found
  • {self.submissions_found} submissions found (your own)
  • {self.announcements_found} announcements found
  • {self.discussions_found} discussions found
  • {self.pages_found} pages found
  • {self.modules_found} modules found
  • {self.module_items_found} module items found

Files Downloaded:
  • {self.files_downloaded} course files downloaded
  • {self.attachments_downloaded} assignment attachments downloaded"""

        if singlefile_enabled:
            summary_text += f"\n  • {self.html_pages_downloaded} HTML pages captured"

        summary_text += f"""

Data Exports Created:
  • {self.json_files_created} JSON data files created
  • Individual course data: {dl_location}/[Term]/[Course]/[Course].json
  • Combined data: {dl_location}/all_output.json

Student Account Limitations: {self.student_limitation_warnings} (expected)
Errors Encountered: {self.error_count}
"""
        return summary_text

# Global stats tracker
extraction_stats = ExtractionStats()

def _load_credentials(path: str) -> dict:
    """Return a dict with API_URL, API_KEY, USER_ID, COOKIES_PATH or empty dict if file missing."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.full_load(f) or {}
    except FileNotFoundError:
        return {}

# Placeholder globals – will be overwritten in __main__ once we have parsed CLI args.
API_URL = ""
API_KEY = ""
USER_ID = 0
COOKIES_PATH = ""

# Directory in which to download course information to (will be created if not
# present)
DL_LOCATION = "./output"
# List of Course IDs that should be skipped
COURSES_TO_SKIP = []

DATE_TEMPLATE = "%B %d, %Y %I:%M %p"

# Max PATH length is 260 characters on Windows. 70 is just an estimate for a reasonable max folder name to prevent the chance of reaching the limit
# Applies to modules, assignments, announcements, and discussions
# If a folder exceeds this limit, a "-" will be added to the end to indicate it was shortened ("..." not valid)
MAX_FOLDER_NAME_SIZE = 70

# Global flag to stop HTML downloads if cookies are invalid
stop_html_downloads = False


class moduleItemView():
    id = 0
    
    title = ""
    content_type = ""
    
    url = ""
    external_url = ""


class moduleView():
    id = 0

    name = ""
    items = []

    def __init__(self):
        self.items = []


class pageView():
    id = 0

    title = ""
    body = ""
    created_date = ""
    last_updated_date = ""


class topicReplyView():
    id = 0

    author = ""
    posted_date = ""
    body = ""


class topicEntryView():
    id = 0

    author = ""
    posted_date = ""
    body = ""
    topic_replies = []

    def __init__(self):
        self.topic_replies = []


class discussionView():
    id = 0

    title = ""
    author = ""
    posted_date = ""
    body = ""
    topic_entries = []

    url = ""
    amount_pages = 0

    def __init__(self):
        self.topic_entries = []


class submissionView():
    id = 0

    attachments = []
    grade = ""
    raw_score = ""
    submission_comments = ""
    total_possible_points = ""
    attempt = 0
    user_id = "no-id"

    preview_url = ""
    ext_url = ""

    def __init__(self):
        self.attachments = []

class attachmentView():
    id = 0

    filename = ""
    url = ""

class assignmentView():
    id = 0

    title = ""
    description = ""
    assigned_date = ""
    due_date = ""
    submissions = []

    html_url = ""
    ext_url = ""
    updated_url = ""
    
    def __init__(self):
        self.submissions = []


class courseView():
    course_id = 0
    
    term = ""
    course_code = ""
    name = ""
    assignments = []
    announcements = []
    discussions = []
    modules = []

    def __init__(self):
        self.assignments = []
        self.announcements = []
        self.discussions = []
        self.modules = []

def makeValidFilename(input_str):
    if(not input_str):
        return input_str

    # Remove invalid characters
    valid_chars = "-_.() %s%s" % (string.ascii_letters, string.digits)
    input_str = input_str.replace("+"," ") # Canvas default for spaces
    input_str = input_str.replace(":","-")
    input_str = input_str.replace("/","-")
    input_str = "".join(c for c in input_str if c in valid_chars)

    # Remove leading and trailing whitespace
    input_str = input_str.lstrip().rstrip()

    # Remove trailing periods
    input_str = input_str.rstrip(".")

    return input_str

def makeValidFolderPath(input_str):
    # Remove invalid characters
    valid_chars = "-_.()/ %s%s" % (string.ascii_letters, string.digits)
    input_str = input_str.replace("+"," ") # Canvas default for spaces
    input_str = input_str.replace(":","-")
    input_str = "".join(c for c in input_str if c in valid_chars)

    # Remove leading and trailing whitespace, separators
    input_str = input_str.lstrip().rstrip().strip("/").strip("\\")

    # Remove trailing periods
    input_str = input_str.rstrip(".")

    # Replace path separators with OS default
    input_str=input_str.replace("/",os.sep)

    return input_str

def shortenFileName(string, shorten_by) -> str:
    if (not string or shorten_by <= 0):
        return string

    # Shorten string by specified value + 1 for "-" to indicate incomplete file name (trailing periods not allowed)
    string = string[:len(string)-(shorten_by + 1)]

    string = string.rstrip().rstrip(".").rstrip("-")
    string += "-"
    
    return string


def findCourseModules(course, course_view):
    modules_dir = os.path.join(DL_LOCATION, course_view.term,
                               course_view.course_code, "modules")

    # Create modules directory if not present
    if not os.path.exists(modules_dir):
        os.makedirs(modules_dir)

    module_views = []

    try:
        modules = course.get_modules()
        modules_list = list(modules)  # Convert to list to get count
        
        if not modules_list:
            print("    No modules found in this course")
        else:
            print(f"    Found {len(modules_list)} modules")

        for module in modules_list:
            module_view = moduleView()

            # ID
            module_view.id = module.id if hasattr(module, "id") else 0

            # Name
            module_view.name = str(module.name) if hasattr(module, "name") else ""
            print(f"      Processing module: {module_view.name}")

            try:
                # Get module items
                module_items = module.get_module_items()
                module_items_list = list(module_items)
                
                if module_items_list:
                    print(f"        Found {len(module_items_list)} items")
                
                for module_item in module_items_list:
                    module_item_view = moduleItemView()

                    # ID
                    module_item_view.id = module_item.id if hasattr(module_item, "id") else 0

                    # Title
                    module_item_view.title = str(module_item.title) if hasattr(module_item, "title") else ""
                    # Type
                    module_item_view.content_type = str(module_item.type) if hasattr(module_item, "type") else ""

                    # URL
                    module_item_view.url = str(module_item.html_url) if hasattr(module_item, "html_url") else ""
                    # External URL
                    module_item_view.external_url = str(module_item.external_url) if hasattr(module_item, "external_url") else ""

                    if module_item_view.content_type == "File":
                        # If problems arise due to long pathnames, changing module.name to module.id might help
                        # A change would also have to be made in downloadCourseModulePages(api_url, course_view, cookies_path)
                        module_name = makeValidFilename(str(module.name))
                        module_name = shortenFileName(module_name, len(module_name) - MAX_FOLDER_NAME_SIZE)
                        module_dir = os.path.join(modules_dir, module_name, "files")

                        try:
                            # Create directory for current module if not present
                            if not os.path.exists(module_dir):
                                os.makedirs(module_dir)

                            # Get the file object
                            module_file = course.get_file(str(module_item.content_id))

                            # Create path for module file download
                            module_file_path = os.path.join(module_dir, makeValidFilename(str(module_file.display_name)))

                            # Download file if it doesn't already exist
                            if not os.path.exists(module_file_path):
                                module_file.download(module_file_path)
                                extraction_stats.files_downloaded += 1
                                print(f"        Downloaded: {module_file.display_name}")
                            else:
                                print(f"        File already exists: {module_file.display_name}")
                        except Exception as e:
                            error_type, message = CanvasErrorHandler.handle_canvas_exception(
                                e, "module file download"
                            )
                            if error_type == "student_limitation":
                                extraction_stats.student_limitation_warnings += 1
                            elif error_type == "not_found":
                                pass  # Already handled by log_error
                            else:
                                extraction_stats.error_count += 1
                            CanvasErrorHandler.log_error(error_type, message)

                    module_view.items.append(module_item_view)
                    extraction_stats.module_items_found += 1
            except Exception as e:
                error_type, message = CanvasErrorHandler.handle_canvas_exception(
                    e, "module item processing"
                )
                CanvasErrorHandler.log_error(error_type, message, verbose=args.verbose)
                extraction_stats.error_count += 1

            module_views.append(module_view)
            extraction_stats.modules_found += 1

    except Exception as e:
        error_type, message = CanvasErrorHandler.handle_canvas_exception(
            e, "module processing"
        )
        CanvasErrorHandler.log_error(error_type, message, verbose=args.verbose)
        extraction_stats.error_count += 1

    return module_views


def downloadCourseFiles(course, course_view):
    # file full_name starts with "course files"
    dl_dir = os.path.join(DL_LOCATION, course_view.term,
                          course_view.course_code)

    # Create directory if not present
    if not os.path.exists(dl_dir):
        os.makedirs(dl_dir)

    try:
        files = course.get_files()
        files_list = list(files)  # Convert to list for consistency and count

        for file in files_list:
            file_folder=course.get_folder(file.folder_id)
            
            folder_dl_dir=os.path.join(dl_dir, makeValidFolderPath(file_folder.full_name))
            
            if not os.path.exists(folder_dl_dir):
                os.makedirs(folder_dl_dir)
        
            dl_path = os.path.join(folder_dl_dir, makeValidFilename(str(file.display_name)))
            
            print(f"    Downloading: {file.display_name}...")
            if not os.path.exists(dl_path):
                try:
                    file.download(dl_path)
                    extraction_stats.files_downloaded += 1
                    print(f"      ✓ Saved: {file.display_name}")
                except Exception as e:
                    error_type, message = CanvasErrorHandler.handle_canvas_exception(e, f"file download for {file.display_name}")
                    CanvasErrorHandler.log_error(error_type, message, verbose=args.verbose)
                    extraction_stats.error_count += 1
            else:
                print(f"      ✓ Already exists: {file.display_name}")

    except Exception as e:
        error_type, message = CanvasErrorHandler.handle_canvas_exception(
            e, "course file download"
        )
        if error_type == "student_limitation":
            extraction_stats.student_limitation_warnings += 1
        else:
            extraction_stats.error_count += 1
        CanvasErrorHandler.log_error(error_type, message, verbose=args.verbose)


def download_submission_attachments(course, course_view):
    course_dir = os.path.join(DL_LOCATION, course_view.term,
                              course_view.course_code)

    # Create directory if not present
    if not os.path.exists(course_dir):
        os.makedirs(course_dir)

    for assignment in course_view.assignments:
        for submission in assignment.submissions:
            assignment_title = makeValidFilename(str(assignment.title))
            assignment_title = shortenFileName(assignment_title, len(assignment_title) - MAX_FOLDER_NAME_SIZE)
            attachment_dir = os.path.join(course_dir, "assignments", assignment_title)
            if(len(assignment.submissions)!=1):
                attachment_dir = os.path.join(attachment_dir,str(submission.user_id))
            if (not os.path.exists(attachment_dir)) and (submission.attachments):
                os.makedirs(attachment_dir)
            for attachment in submission.attachments:
                filepath = os.path.join(attachment_dir, makeValidFilename(str(attachment.id) +
                                        "_" + attachment.filename))
                
                print(f"    Downloading attachment: {attachment.filename}...")
                if not os.path.exists(filepath):
                    try:
                        r = requests.get(attachment.url, allow_redirects=True)
                        r.raise_for_status()
                        with open(filepath, 'wb') as f:
                            f.write(r.content)
                        extraction_stats.attachments_downloaded += 1
                        print(f"      ✓ Saved: {attachment.filename}")
                    except Exception as e:
                        print(f"      ❌ Failed to download {attachment.filename}: {e}")
                        extraction_stats.error_count += 1
                else:
                    print(f"      ✓ Already exists: {attachment.filename}")


def getCoursePageUrls(course):
    page_urls = []

    try:
        # Get all pages
        pages = course.get_pages()

        for page in pages:
            if hasattr(page, "url"):
                page_urls.append(str(page.url))
    except Exception as e:
        error_msg = str(e)
        if "Not Found" not in error_msg:
            error_type, message = CanvasErrorHandler.handle_canvas_exception(
                e, "page URL retrieval"
            )
            CanvasErrorHandler.log_error(error_type, message, verbose=args.verbose)
            if error_type != "student_limitation":
                extraction_stats.error_count += 1
            else:
                extraction_stats.student_limitation_warnings += 1

    return page_urls


def findCoursePages(course):
    page_views = []

    try:
        # Get all page URLs
        page_urls = getCoursePageUrls(course)

        for url in page_urls:
            page = course.get_page(url)

            page_view = pageView()

            # ID
            page_view.id = page.id if hasattr(page, "id") else 0

            # Title
            page_view.title = str(page.title) if hasattr(page, "title") else ""
            # Body
            page_view.body = str(page.body) if hasattr(page, "body") else ""
            # Date created
            try:
                page_view.created_date = dateutil.parser.parse(page.created_at).strftime(DATE_TEMPLATE) if \
                    hasattr(page, "created_at") else ""
            except (ValueError, TypeError):
                page_view.created_date = ""
                
            # Date last updated
            try:
                page_view.last_updated_date = dateutil.parser.parse(page.updated_at).strftime(DATE_TEMPLATE) if \
                    hasattr(page, "updated_at") else ""
            except (ValueError, TypeError):
                page_view.last_updated_date = ""

            page_views.append(page_view)
            extraction_stats.pages_found += 1
    except Exception as e:
        error_type, message = CanvasErrorHandler.handle_canvas_exception(
            e, "page download"
        )
        CanvasErrorHandler.log_error(error_type, message, verbose=args.verbose)
        extraction_stats.error_count += 1

    return page_views


def findCourseAssignments(course):
    assignment_views = []

    # Get all assignments
    assignments = course.get_assignments()
    assignments_list = list(assignments)  # Convert to list for consistency
    
    try:
        for assignment in assignments_list:
            # Create a new assignment view
            assignment_view = assignmentView()

            #ID
            assignment_view.id = assignment.id if \
                hasattr(assignment, "id") else 0

            # Title
            assignment_view.title = makeValidFilename(str(assignment.name)) if \
                hasattr(assignment, "name") else ""
            # Description
            assignment_view.description = str(assignment.description) if \
                hasattr(assignment, "description") else ""
            
            # Assigned date
            try:
                assignment_view.assigned_date = dateutil.parser.parse(assignment.created_at).strftime(DATE_TEMPLATE) if \
                    hasattr(assignment, "created_at") and assignment.created_at else ""
            except (ValueError, TypeError):
                assignment_view.assigned_date = ""
            
            # Due date
            try:
                assignment_view.due_date = dateutil.parser.parse(assignment.due_at).strftime(DATE_TEMPLATE) if \
                    hasattr(assignment, "due_at") and assignment.due_at else ""
            except (ValueError, TypeError):
                assignment_view.due_date = ""

            # HTML Url
            assignment_view.html_url = assignment.html_url if \
                hasattr(assignment, "html_url") else ""   
            # External URL
            assignment_view.ext_url = str(assignment.url) if \
                hasattr(assignment, "url") else ""
            # Other URL (more up-to-date)
            assignment_view.updated_url = str(assignment.submissions_download_url).split("submissions?")[0] if \
                hasattr(assignment, "submissions_download_url") else ""

            try:
                try: # Download all submissions for entire class
                    submissions = assignment.get_submissions()
                    submissions[0] # Trigger Unauthorized if not allowed
                except (Unauthorized, Forbidden) as e:
                    error_type, message = CanvasErrorHandler.handle_canvas_exception(
                        e, "class submission download"
                    )
                    if error_type == "student_limitation":
                        extraction_stats.student_limitation_warnings += 1
                        if extraction_stats.student_limitation_warnings == 1:
                            print(f"    Note: Not authorized to download every student's assignment submission. Downloading submission for user {USER_ID} only.")
                    else:
                        CanvasErrorHandler.log_error(error_type, message, verbose=args.verbose)
                        extraction_stats.error_count += 1
                    
                    # Download submission for this user only
                    submissions = [assignment.get_submission(USER_ID)]
                submissions[0] #throw error if no submissions found at all but without error
            except (ResourceDoesNotExist, NameError, IndexError) as e:
                error_type, message = CanvasErrorHandler.handle_canvas_exception(
                    e, "submission retrieval"
                )
                CanvasErrorHandler.log_error(error_type, message, verbose=args.verbose)
                extraction_stats.error_count += 1
            except Exception as e:
                error_type, message = CanvasErrorHandler.handle_canvas_exception(
                    e, "submission retrieval"
                )
                CanvasErrorHandler.log_error(error_type, message, verbose=args.verbose)
                extraction_stats.error_count += 1
            else:
                try:
                    for submission in submissions:

                        sub_view = submissionView()

                        # Submission ID
                        sub_view.id = submission.id if \
                            hasattr(submission, "id") else 0
                            
                        # My grade
                        sub_view.grade = str(submission.grade) if \
                            hasattr(submission, "grade") else ""
                        # My raw score
                        sub_view.raw_score = str(submission.score) if \
                            hasattr(submission, "score") else ""
                        # Total possible score
                        sub_view.total_possible_points = str(assignment.points_possible) if \
                            hasattr(assignment, "points_possible") else ""
                        # Submission comments
                        sub_view.submission_comments = str(submission.submission_comments) if \
                            hasattr(submission, "submission_comments") else ""
                        # Attempt
                        sub_view.attempt = submission.attempt if \
                            hasattr(submission, "attempt") and submission.attempt is not None else 0
                        # User ID
                        sub_view.user_id = str(submission.user_id) if \
                            hasattr(submission, "user_id") else ""
                            
                        # Submission URL
                        sub_view.preview_url = str(submission.preview_url) if \
                            hasattr(submission, "preview_url") else ""
                        #   External URL
                        sub_view.ext_url = str(submission.url) if \
                            hasattr(submission, "url") else ""

                        try:
                            submission.attachments
                        except AttributeError:
                            pass  # No attachments message removed for cleaner output
                        else:
                            attachment_count = len(submission.attachments) if submission.attachments else 0
                            if attachment_count > 0:
                                print(f"        Found {attachment_count} attachments")
                            for attachment in submission.attachments:
                                attach_view = attachmentView()
                                attach_view.url = attachment.url
                                attach_view.id = attachment.id
                                attach_view.filename = attachment.filename
                                sub_view.attachments.append(attach_view)
                            assignment_view.submissions.append(sub_view)
                            extraction_stats.submissions_found += 1
                except Exception as e:
                    error_type, message = CanvasErrorHandler.handle_canvas_exception(
                        e, "submission processing"
                    )
                    CanvasErrorHandler.log_error(error_type, message, verbose=args.verbose)
                    extraction_stats.error_count += 1

            assignment_views.append(assignment_view)
            extraction_stats.assignments_found += 1
    except Exception as e:
        error_type, message = CanvasErrorHandler.handle_canvas_exception(
            e, "course assignments processing"
        )
        CanvasErrorHandler.log_error(error_type, message, verbose=args.verbose)
        extraction_stats.error_count += 1

    return assignment_views


def findCourseAnnouncements(course):
    announcement_views = []

    try:
        announcements = course.get_discussion_topics(only_announcements=True)

        for announcement in announcements:
            discussion_view = getDiscussionView(announcement)

            announcement_views.append(discussion_view)
            extraction_stats.announcements_found += 1
    except Exception as e:
        error_type, message = CanvasErrorHandler.handle_canvas_exception(
            e, "announcement processing"
        )
        CanvasErrorHandler.log_error(error_type, message, verbose=args.verbose)
        extraction_stats.error_count += 1

    return announcement_views


def getDiscussionView(discussion_topic):
    # Create discussion view
    discussion_view = discussionView()

    #ID
    discussion_view.id = discussion_topic.id if hasattr(discussion_topic, "id") else 0

    # Title
    discussion_view.title = str(discussion_topic.title) if hasattr(discussion_topic, "title") else ""
    # Author
    discussion_view.author = str(discussion_topic.user_name) if hasattr(discussion_topic, "user_name") else ""
    # Posted date
    try:
        discussion_view.posted_date = dateutil.parser.parse(discussion_topic.created_at).strftime("%B %d, %Y %I:%M %p") if \
            hasattr(discussion_topic, "created_at") and discussion_topic.created_at else ""
    except (ValueError, TypeError):
        discussion_view.posted_date = ""
    # Body
    discussion_view.body = str(discussion_topic.message) if hasattr(discussion_topic, "message") else ""

    # URL
    discussion_view.url = str(discussion_topic.html_url) if hasattr(discussion_topic, "html_url") else ""
    
    # Keeps track of how many topic_entries there are.
    topic_entries_counter = 0

    # Topic entries
    if hasattr(discussion_topic, "discussion_subentry_count") and discussion_topic.discussion_subentry_count > 0:
        # Need to get replies to entries recursively?

        discussion_topic_entries = discussion_topic.get_topic_entries()

        try:
            for topic_entry in discussion_topic_entries:
                topic_entries_counter += 1
                
                # Create new discussion view for the topic_entry
                topic_entry_view = topicEntryView()

                # ID
                topic_entry_view.id = topic_entry.id if hasattr(topic_entry, "id") else 0
                # Author
                topic_entry_view.author = str(topic_entry.user_name) if hasattr(topic_entry, "user_name") else ""
                # Posted date
                try:
                    topic_entry_view.posted_date = dateutil.parser.parse(topic_entry.created_at).strftime("%B %d, %Y %I:%M %p") if \
                        hasattr(topic_entry, "created_at") and topic_entry.created_at else ""
                except (ValueError, TypeError):
                    topic_entry_view.posted_date = ""
                # Body
                topic_entry_view.body = str(topic_entry.message) if hasattr(topic_entry, "message") else ""

                # Get this topic's replies
                topic_entry_replies = topic_entry.get_replies()

                try:
                    for topic_reply in topic_entry_replies:
                        # Create new topic reply view
                        topic_reply_view = topicReplyView()
                        
                        # ID
                        topic_reply_view.id = topic_reply.id if hasattr(topic_reply, "id") else 0

                        # Author
                        topic_reply_view.author = str(topic_reply.user_name) if hasattr(topic_reply, "user_name") else ""
                        # Posted Date
                        try:
                            topic_reply_view.posted_date = dateutil.parser.parse(topic_reply.created_at).strftime("%B %d, %Y %I:%M %p") if \
                                hasattr(topic_reply, "created_at") and topic_reply.created_at else ""
                        except (ValueError, TypeError):
                            topic_reply_view.posted_date = ""
                        # Body
                        topic_reply_view.body = str(topic_reply.message) if hasattr(topic_reply, "message") else ""

                        topic_entry_view.topic_replies.append(topic_reply_view)
                except Exception as e:
                    error_type, message = CanvasErrorHandler.handle_canvas_exception(
                        e, "discussion topic reply processing"
                    )
                    CanvasErrorHandler.log_error(error_type, message, verbose=args.verbose)
                    extraction_stats.error_count += 1

                discussion_view.topic_entries.append(topic_entry_view)
        except Exception as e:
            error_type, message = CanvasErrorHandler.handle_canvas_exception(
                e, "discussion topic entry processing"
            )
            CanvasErrorHandler.log_error(error_type, message, verbose=args.verbose)
            extraction_stats.error_count += 1
        
    # Amount of pages  
    discussion_view.amount_pages = int(topic_entries_counter/50) + 1 # Typically 50 topic entries are stored on a page before it creates another page.
    
    return discussion_view


def findCourseDiscussions(course):
    discussion_views = []

    try:
        discussion_topics = course.get_discussion_topics()

        for discussion_topic in discussion_topics:
            discussion_view = None
            discussion_view = getDiscussionView(discussion_topic)

            discussion_views.append(discussion_view)
            extraction_stats.discussions_found += 1
    except Exception as e:
        error_type, message = CanvasErrorHandler.handle_canvas_exception(
            e, "discussion processing"
        )
        CanvasErrorHandler.log_error(error_type, message, verbose=args.verbose)
        extraction_stats.error_count += 1

    return discussion_views


def getCourseView(course):
    course_view = courseView()

    # Course ID
    course_view.course_id = course.id if hasattr(course, "id") else 0

    # Course term
    course_view.term = makeValidFilename(course.term.name if hasattr(course, "term") and hasattr(course.term, "name") else "")

    # Course code
    course_view.course_code = makeValidFilename(course.course_code if hasattr(course, "course_code") else "")

    # Course name
    course_view.name = course.name if hasattr(course, "name") else ""

    print(f"Working on: {course_view.term}: {course_view.name}")

    # Track HTML pages saved per course
    html_pages_saved_in_course = 0

    # Course assignments
    print("  Getting assignments")
    course_view.assignments = findCourseAssignments(course)
    print(f"    Found {len(course_view.assignments)} assignments")

    # Course announcements
    print("  Getting announcements")
    course_view.announcements = findCourseAnnouncements(course)
    print(f"    Found {len(course_view.announcements)} announcements")

    # Course discussions
    print("  Getting discussions")
    course_view.discussions = findCourseDiscussions(course)
    print(f"    Found {len(course_view.discussions)} discussions")

    # Course pages
    print("  Getting pages")
    course_view.pages = findCoursePages(course)
    print(f"    Found {len(course_view.pages)} pages")

    return course_view


def exportAllCourseData(course_view):
    json_str = json.dumps(json.loads(jsonpickle.encode(course_view, unpicklable = False)), indent = 4)

    course_output_dir = os.path.join(DL_LOCATION, course_view.term,
                                     course_view.course_code)

    # Create directory if not present
    if not os.path.exists(course_output_dir):
        os.makedirs(course_output_dir)

    course_output_path = os.path.join(course_output_dir,
                                      course_view.course_code + ".json")

    print(f"    Exporting JSON data for {course_view.course_code}...")
    with open(course_output_path, "w") as out_file:
        out_file.write(json_str)
        
    extraction_stats.json_files_created += 1
    print(f"      ✓ Data saved to: {course_output_path}")

def _download_page_if_not_exists(url, output_path, cookies_path, additional_args=(), verbose=False):
    """
    Downloads a single HTML page if it doesn't exist, updating stats.
    Returns True if downloaded, False otherwise.
    """
    global stop_html_downloads
    if stop_html_downloads:
        return False
        
    filename = os.path.basename(output_path)
    print(f"    Downloading: {filename}...")

    if not os.path.exists(output_path):
        output_dir = os.path.dirname(output_path)
        os.makedirs(output_dir, exist_ok=True)
        
        try:
            download_page(url, cookies_path, output_dir, filename, additional_args, verbose)
            extraction_stats.html_pages_downloaded += 1
            print(f"      ✓ Saved: {filename}")
            return True
        except Exception as e:
            print(f"      ❌ Failed: {e}")
            extraction_stats.error_count += 1
            if "Authentication failed" in str(e):
                print("      Stopping all subsequent HTML downloads.")
                stop_html_downloads = True
            return False
    else:
        print(f"      ✓ Already exists: {filename}")
        return True # Return True because the file exists, which is a success condition for the caller

def downloadCourseHTML(api_url, cookies_path, verbose=False):
    if not cookies_path or stop_html_downloads:
        return 0
    
    course_list_path = os.path.join(DL_LOCATION, "course_list.html")
    url = f"{api_url}/courses/"
    
    if _download_page_if_not_exists(url, course_list_path, cookies_path, verbose=verbose):
        return 1
    return 0

def downloadCourseHomePageHTML(api_url, course_view, cookies_path, verbose=False):
    if not cookies_path or stop_html_downloads:
        return 0

    dl_dir = os.path.join(DL_LOCATION, course_view.term, course_view.course_code)
    homepage_path = os.path.join(dl_dir, "homepage.html")
    url = f"{api_url}/courses/{course_view.course_id}"
    
    if _download_page_if_not_exists(url, homepage_path, cookies_path, verbose=verbose):
        return 1
    return 0

def downloadCourseGradesHTML(api_url, course_view, cookies_path, verbose=False):
    if not cookies_path or stop_html_downloads:
        return 0

    dl_dir = os.path.join(DL_LOCATION, course_view.term,
                         course_view.course_code)
    grades_path = os.path.join(dl_dir, "grades.html")
    url = f"{api_url}/courses/{course_view.course_id}/grades"
    additional_args=("--remove-hidden-elements=false",)

    if _download_page_if_not_exists(url, grades_path, cookies_path, additional_args, verbose=verbose):
        # We only proceed with BeautifulSoup modifications if the file was newly downloaded or already existed.
        with open(grades_path, "r+t", encoding="utf-8") as grades_file:
            grades_html = BeautifulSoup(grades_file, "html.parser")

            button = grades_html.select_one("#show_all_details_button")
            if button is not None:
                button_class = button.get_attribute_list("class", [])
                if "showAll" not in button_class:
                    button_class.append("showAll")
                button["class"] = button_class
                button.string = "Hide All Details" # Unfortunately this cannot handle i18n.

            assignments = grades_html.select("tr.student_assignment.editable")
            for assignment in assignments:
                assignment_id = str(assignment.get("id", "")).removeprefix("submission_")
                muted = str(assignment.get("data-muted", "")).casefold() in {"true"}
                if not muted:
                    for element in itertools.chain(
                        grades_html.select(f"#comments_thread_{assignment_id}"),
                        grades_html.select(f"#rubric_{assignment_id}"),
                        grades_html.select(f"#grade_info_{assignment_id}"),
                        grades_html.select(f"#final_grade_info_{assignment_id}"),
                        grades_html.select(f".parent_assignment_id_{assignment_id}"),
                    ):
                        element_style = str(element.get("style", ""))
                        element_style = re.sub(r"display:\s*none", "", element_style)
                        element["style"] = element_style

                    assignment_arrow = grades_html.select_one(f"#parent_assignment_id_{assignment_id} i")
                    if assignment_arrow is not None:
                        assignment_arrow_class = assignment_arrow.get_attribute_list("class", [])
                        assignment_arrow_class.remove("icon-arrow-open-end")
                        assignment_arrow_class.append("icon-arrow-open-down")
                        assignment_arrow["class"] = assignment_arrow_class

            grades_file.seek(0)
            grades_file.write(grades_html.prettify(formatter="html"))
            grades_file.truncate()
        return 1
    return 0
        
def downloadAssignmentPages(api_url, course_view, cookies_path, verbose=False):
    pages_saved = 0
    if not cookies_path or not course_view.assignments or stop_html_downloads:
        return pages_saved

    base_assign_dir = os.path.join(DL_LOCATION, course_view.term,
        course_view.course_code, "assignments")

    # Download assignment list page
    assignment_list_path = os.path.join(base_assign_dir, "assignment_list.html")
    list_url = f"{api_url}/courses/{course_view.course_id}/assignments/"
    if _download_page_if_not_exists(list_url, assignment_list_path, cookies_path, verbose=verbose):
        pages_saved += 1

    for assignment in course_view.assignments:
        assignment_title = makeValidFilename(str(assignment.title))
        assignment_title = shortenFileName(assignment_title, len(assignment_title) - MAX_FOLDER_NAME_SIZE)  
        assign_dir = os.path.join(base_assign_dir, assignment_title)

        if assignment.html_url:
            assignment_page_path = os.path.join(assign_dir, "assignment.html")
            if _download_page_if_not_exists(assignment.html_url, assignment_page_path, cookies_path, verbose=verbose):
                pages_saved += 1

        for submission in assignment.submissions:
            submission_dir = assign_dir

            if len(assignment.submissions) != 1:
                submission_dir = os.path.join(assign_dir, str(submission.user_id))

            if submission.preview_url:
                submission_page_path = os.path.join(submission_dir, "submission.html")
                if _download_page_if_not_exists(submission.preview_url, submission_page_path, cookies_path, verbose=verbose):
                    pages_saved += 1

            if (submission.attempt and submission.attempt > 1 and assignment.updated_url and assignment.html_url 
                and assignment.html_url.rstrip("/") != assignment.updated_url.rstrip("/")):
                attempts_dir = os.path.join(assign_dir, "attempts")
                
                for i in range(submission.attempt):
                    filename = f"attempt_{i+1}.html"
                    attempt_path = os.path.join(attempts_dir, filename)
                    attempt_url = f"{assignment.updated_url}/history?version={i+1}"
                    if _download_page_if_not_exists(attempt_url, attempt_path, cookies_path, verbose=verbose):
                        pages_saved += 1
    return pages_saved

def downloadCourseModulePages(api_url, course_view, cookies_path, verbose=False): 
    pages_saved = 0
    if not cookies_path or not course_view.modules or stop_html_downloads:
        return pages_saved

    modules_dir = os.path.join(DL_LOCATION, course_view.term,
        course_view.course_code, "modules")

    # Downloads the modules page
    module_list_path = os.path.join(modules_dir, "modules_list.html")
    list_url = f"{api_url}/courses/{course_view.course_id}/modules/"
    if _download_page_if_not_exists(list_url, module_list_path, cookies_path, verbose=verbose):
        pages_saved += 1

    for module in course_view.modules:
        for item in module.items:
            module_name = makeValidFilename(str(module.name))
            module_name = shortenFileName(module_name, len(module_name) - MAX_FOLDER_NAME_SIZE)
            items_dir = os.path.join(modules_dir, module_name)
            
            if item.url:
                filename = makeValidFilename(str(item.title)) + ".html"
                module_item_path = os.path.join(items_dir, filename)
                if _download_page_if_not_exists(item.url, module_item_path, cookies_path, verbose=verbose):
                    pages_saved += 1
    return pages_saved

def downloadCourseAnnouncementPages(api_url, course_view, cookies_path, verbose=False):
    pages_saved = 0
    if not cookies_path or not course_view.announcements or stop_html_downloads:
        return pages_saved

    base_announce_dir = os.path.join(DL_LOCATION, course_view.term,
        course_view.course_code, "announcements")

    # Download announcement list
    announcement_list_path = os.path.join(base_announce_dir, "announcement_list.html")
    list_url = f"{api_url}/courses/{course_view.course_id}/announcements/"
    if _download_page_if_not_exists(list_url, announcement_list_path, cookies_path, verbose=verbose):
        pages_saved += 1

    for announcement in course_view.announcements:
        if not announcement.url:
            continue

        announcements_title = makeValidFilename(str(announcement.title))
        announcements_title = shortenFileName(announcements_title, len(announcements_title) - MAX_FOLDER_NAME_SIZE)
        announce_dir = os.path.join(base_announce_dir, announcements_title)

        if not os.path.exists(announce_dir):
            os.makedirs(announce_dir)

        for i in range(announcement.amount_pages):
            filename = f"announcement_{i+1}.html"
            page_path = os.path.join(announce_dir, filename)
            page_url = f"{announcement.url}/page-{i+1}"
            if _download_page_if_not_exists(page_url, page_path, cookies_path, verbose=verbose):
                pages_saved += 1
    return pages_saved
        
def downloadCourseDiscussionPages(api_url, course_view, cookies_path, verbose=False):
    pages_saved = 0
    if not cookies_path or not course_view.discussions or stop_html_downloads:
        return pages_saved

    base_discussion_dir = os.path.join(DL_LOCATION, course_view.term,
        course_view.course_code, "discussions")

    # Download discussion list
    discussion_list_path = os.path.join(base_discussion_dir, "discussion_list.html")
    list_url = f"{api_url}/courses/{course_view.course_id}/discussion_topics/"
    if _download_page_if_not_exists(list_url, discussion_list_path, cookies_path, verbose=verbose):
        pages_saved += 1

    for discussion in course_view.discussions:
        if not discussion.url:
            continue

        discussion_title = makeValidFilename(str(discussion.title))
        discussion_title = shortenFileName(discussion_title, len(discussion_title) - MAX_FOLDER_NAME_SIZE)
        discussion_dir = os.path.join(base_discussion_dir, discussion_title)

        if not os.path.exists(discussion_dir):
            os.makedirs(discussion_dir)

        for i in range(discussion.amount_pages):
            filename = f"discussion_{i+1}.html"
            page_path = os.path.join(discussion_dir, filename)
            page_url = f"{discussion.url}/page-{i+1}"
            if _download_page_if_not_exists(page_url, page_path, cookies_path, verbose=verbose):
                pages_saved += 1
    return pages_saved

if __name__ == "__main__":

    print("Welcome to the Canvas Student Data Export Tool\n")

    parser = argparse.ArgumentParser(description="Export nearly all of a student's Canvas LMS data.")
    parser.add_argument("-c", "--config", default="credentials.yaml", help="Path to YAML credentials file (default: credentials.yaml)")
    parser.add_argument("-o", "--output", default="./output", help="Directory to store exported data (default: ./output)")
    parser.add_argument("--singlefile", action="store_true", help="Enable HTML snapshot capture with SingleFile.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output for debugging.")
    parser.add_argument("--version", action="version", version="Canvas Student Data Export Tool 1.0")

    args = parser.parse_args()

    # Load credentials from YAML
    creds = _load_credentials(args.config)
    
    # Validate credentials
    required = ["API_URL", "API_KEY", "USER_ID"]
    missing = [k for k in required if not creds.get(k)]

    # COOKIES_PATH is required if singlefile is active, but it can be missing.
    if args.singlefile:
        print("Note: --singlefile is enabled. Please ensure your browser cookies")
        print("      are fresh by logging into Canvas and then re-exporting")
        print("      them using the chrome extension right before running this script.\n")
        input("Press Enter to continue...")
        if "COOKIES_PATH" not in creds or not creds["COOKIES_PATH"]:
            missing.append("COOKIES_PATH")

    if missing:
        print(f"Error: {args.config} is missing required field(s): {', '.join(missing)}.")
        print("Please create the YAML file with the following structure:\n"
              "API_URL: https://<your>.instructure.com\n"
              "API_KEY: <your key>\n"
              "USER_ID: 123456\n"
              "COOKIES_PATH: path/to/cookies.txt\n")
        sys.exit(1)

    # Populate globals expected throughout the script
    API_URL = creds["API_URL"].strip()
    API_KEY = creds["API_KEY"].strip()  # Remove leading/trailing whitespace which is a common issue
    USER_ID = creds["USER_ID"]
    # Use .get() to safely access optional/conditionally required keys
    COOKIES_PATH = creds.get("COOKIES_PATH", "")
    COURSES_TO_SKIP = creds.get("COURSES_TO_SKIP", [])

    chrome_path_override = creds.get("CHROME_PATH")
    if chrome_path_override:
        override_chrome_path(chrome_path_override)

    # Update output directory
    DL_LOCATION = args.output

    print("\nConnecting to Canvas…\n")

    # Initialize a new Canvas object
    canvas = Canvas(API_URL, API_KEY)
    
    # Test the connection and API key
    try:
        user = canvas.get_current_user()
        print(f"Successfully authenticated as: {user.name} (ID: {user.id})")
        if user.id != USER_ID:
            print(f"Warning: Authenticated user ID ({user.id}) does not match configured USER_ID ({USER_ID})")
    except Exception as e:
        error_type, message = CanvasErrorHandler.handle_canvas_exception(
            e, "Canvas authentication"
        )
        if CanvasErrorHandler.is_fatal_error(error_type):
            print(f"FATAL: {message}")
            sys.exit(1)
        else:
            CanvasErrorHandler.log_error(error_type, message, verbose=args.verbose)
 
    print(f"Creating output directory: {DL_LOCATION}\n")
    os.makedirs(DL_LOCATION, exist_ok=True)
 
    all_courses_views = []

    print("Getting list of all courses\n")
    courses_list = [
        canvas.get_courses(enrollment_state = "active", include="term"),
        canvas.get_courses(enrollment_state = "completed", include="term")
    ]

    skip = set(COURSES_TO_SKIP)


    if COOKIES_PATH and args.singlefile:
        print("  Downloading course list page")
        downloadCourseHTML(API_URL, COOKIES_PATH, verbose=args.verbose)

    for courses in courses_list:
        for course in courses:
            if course.id in skip or not hasattr(course, "name") or not hasattr(course, "term"):
                continue
            
            html_pages_saved_in_course = 0

            course_view = getCourseView(course)

            all_courses_views.append(course_view)

            print("  Downloading all files")
            downloadCourseFiles(course, course_view)

            print("  Downloading submission attachments")
            download_submission_attachments(course, course_view)

            print("  Getting modules and downloading module files")
            course_view.modules = findCourseModules(course, course_view)

            if COOKIES_PATH and args.singlefile:
                print("  Downloading course home page")
                html_pages_saved_in_course += downloadCourseHomePageHTML(API_URL, course_view, COOKIES_PATH, verbose=args.verbose)

                print("  Downloading course grades")
                html_pages_saved_in_course += downloadCourseGradesHTML(API_URL, course_view, COOKIES_PATH, verbose=args.verbose)

                print("  Downloading assignment pages")
                html_pages_saved_in_course += downloadAssignmentPages(API_URL, course_view, COOKIES_PATH, verbose=args.verbose)

                print("  Downloading course module pages")
                html_pages_saved_in_course += downloadCourseModulePages(API_URL, course_view, COOKIES_PATH, verbose=args.verbose)

                print("  Downloading course announcements pages")
                html_pages_saved_in_course += downloadCourseAnnouncementPages(API_URL, course_view, COOKIES_PATH, verbose=args.verbose)   

                print("  Downloading course discussion pages")
                html_pages_saved_in_course += downloadCourseDiscussionPages(API_URL, course_view, COOKIES_PATH, verbose=args.verbose)

            print("  Exporting all course data")
            exportAllCourseData(course_view)
            
            # Show mini-summary for this course
            assignments_count = len(course_view.assignments)
            submissions_count = sum(len(a.submissions) for a in course_view.assignments)
            modules_count = len(course_view.modules)
            pages_count = len(course_view.pages)
            announcements_count = len(course_view.announcements)
            discussions_count = len(course_view.discussions)
            
            print(f"  ✓ Course data exported:")
            print(f"    • {assignments_count} assignments with {submissions_count} submissions (JSON)")
            print(f"    • {modules_count} modules (JSON)")
            print(f"    • {pages_count} pages (JSON)")
            print(f"    • {announcements_count} announcements (JSON)")
            print(f"    • {discussions_count} discussions (JSON)")
            if COOKIES_PATH and args.singlefile:
                print(f"    • {html_pages_saved_in_course} HTML snapshots saved")
            print()

    print("Exporting data from all courses combined as one file: "
          "all_output.json")
    json_str = jsonpickle.encode(all_courses_views, unpicklable=False, indent=4)

    all_output_path = os.path.join(DL_LOCATION, "all_output.json")

    with open(all_output_path, "w") as out_file:
        out_file.write(json_str)
    
    extraction_stats.json_files_created += 1
    print(f"Combined JSON data exported to: {all_output_path}")

    print("\nProcess complete. All canvas data exported!")
    print(extraction_stats.summary(DL_LOCATION, singlefile_enabled=args.singlefile))
