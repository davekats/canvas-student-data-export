# built in
import json
import os
import string
import tkinter as tk
from tkinter import filedialog
from tkinter import messagebox
from tkinter import scrolledtext
from tkinter.ttk import Progressbar
import threading
import sys

# external
from canvasapi import Canvas
from canvasapi.exceptions import ResourceDoesNotExist, Unauthorized

from singlefile import download_page

import dateutil.parser
import jsonpickle
import requests
import yaml
import mysql.connector

import shutil


try:
    with open("credentials.yaml", 'r') as f:
        credentials = yaml.full_load(f)
except OSError:
    # Canvas API URL
    API_URL = ""
    # Canvas API key
    API_KEY = ""
    # My Canvas User ID
    USER_ID = 0000000
    # Browser Cookies File
    COOKIES_PATH = ""
else:
    API_URL = credentials["API_URL"]
    API_KEY = credentials["API_KEY"]
    USER_ID = credentials["USER_ID"]
    COOKIES_PATH = credentials["COOKIES_PATH"]

def flag_file_if_needed(filepath):
    """Check the file for specific criteria and flag (copy) if necessary."""
    print(f"Checking file: {filepath}")
   # In this case, we're looking for 'grade' in the filename.
    if 'grade' in os.path.basename(filepath).lower():
        flagged_dir = os.path.join(DL_LOCATION, "flagged_files")
        
        if not os.path.exists(flagged_dir):
            os.makedirs(flagged_dir)
            print(f"Created directory: {flagged_dir}")
        
        # copy the file to the flagged directory
        shutil.copy2(filepath, flagged_dir)

# Directory in which to download course information to (will be created if not
# present)
DL_LOCATION = "./output"
# List of Course IDs that should be skipped (need to be integers)
COURSES_TO_SKIP = [288290, 512033]

DATE_TEMPLATE = "%B %d, %Y %I:%M %p"

# Max PATH length is 260 characters on Windows. 70 is just an estimate for a reasonable max folder name to prevent the chance of reaching the limit
# Applies to modules, assignments, announcements, and discussions
# If a folder exceeds this limit, a "-" will be added to the end to indicate it was shortened ("..." not valid)
MAX_FOLDER_NAME_SIZE = 70


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
    if (not input_str):
        return input_str

    # Remove invalid characters
    valid_chars = "-_.() %s%s" % (string.ascii_letters, string.digits)
    input_str = input_str.replace("+", " ")  # Canvas default for spaces
    input_str = input_str.replace(":", "-")
    input_str = input_str.replace("/", "-")
    input_str = "".join(c for c in input_str if c in valid_chars)

    # Remove leading and trailing whitespace
    input_str = input_str.lstrip().rstrip()

    # Remove trailing periods
    input_str = input_str.rstrip(".")

    return input_str


def makeValidFolderPath(input_str):
    # Remove invalid characters
    valid_chars = "-_.()/ %s%s" % (string.ascii_letters, string.digits)
    input_str = input_str.replace("+", " ")  # Canvas default for spaces
    input_str = input_str.replace(":", "-")
    input_str = "".join(c for c in input_str if c in valid_chars)

    # Remove leading and trailing whitespace, separators
    input_str = input_str.lstrip().rstrip().strip("/").strip("\\")

    # Remove trailing periods
    input_str = input_str.rstrip(".")

    # Replace path separators with OS default
    input_str = input_str.replace("/", os.sep)

    return input_str


def shortenFileName(string, shorten_by) -> str:
    if (not string or shorten_by <= 0):
        return string

    # Shorten string by specified value + 1 for "-" to indicate incomplete file name (trailing periods not allowed)
    string = string[:len(string) - (shorten_by + 1)]

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

        for module in modules:
            module_view = moduleView()

            # ID
            module_view.id = module.id if hasattr(module, "id") else ""

            # Name
            module_view.name = str(module.name) if hasattr(module, "name") else ""

            try:
                # Get module items
                module_items = module.get_module_items()

                for module_item in module_items:
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
                    module_item_view.external_url = str(module_item.external_url) if hasattr(module_item,
                                                                                             "external_url") else ""

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
                            module_file_path = os.path.join(module_dir,
                                                            makeValidFilename(str(module_file.display_name)))

                            # Download file if it doesn't already exist
                            if not os.path.exists(module_file_path):
                                module_file.download(module_file_path)
                        except Exception as e:
                            print("Skipping module file download that gave the following error:")
                            print(e)

                    module_view.items.append(module_item_view)
            except Exception as e:
                print("Skipping module item that gave the following error:")
                print(e)

            module_views.append(module_view)

    except Exception as e:
        print("Skipping entire module that gave the following error:")
        print(e)

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

        for file in files:
            file_folder = course.get_folder(file.folder_id)

            folder_dl_dir = os.path.join(dl_dir, makeValidFolderPath(file_folder.full_name))

            if not os.path.exists(folder_dl_dir):
                os.makedirs(folder_dl_dir)

            dl_path = os.path.join(folder_dl_dir, makeValidFilename(str(file.display_name)))

            # Download file if it doesn't already exist
            if not os.path.exists(dl_path):
                print('Downloading: {}'.format(dl_path))
                file.download(dl_path)
                flag_file_if_needed(dl_path)
    except Exception as e:
        print("Skipping file download that gave the following error:")
        print(e)


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
            if (len(assignment.submissions) != 1):
                attachment_dir = os.path.join(attachment_dir, str(submission.user_id))
            if (not os.path.exists(attachment_dir)) and (submission.attachments):
                os.makedirs(attachment_dir)
            for attachment in submission.attachments:
                filepath = os.path.join(attachment_dir, makeValidFilename(str(attachment.id) +
                                                                          "_" + attachment.filename))
                if not os.path.exists(filepath):
                    print('Downloading attachment: {}'.format(filepath))
                    r = requests.get(attachment.url, allow_redirects=True)
                    with open(filepath, 'wb') as f:
                        f.write(r.content)
                else:
                    print('File already exists: {}'.format(filepath))


def getCoursePageUrls(course):
    page_urls = []

    try:
        # Get all pages
        pages = course.get_pages()

        for page in pages:
            if hasattr(page, "url"):
                page_urls.append(str(page.url))
    except Exception as e:
        if e.message != "Not Found":
            print("Skipping page that gave the following error:")
            print(e)

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
            page_view.created_date = dateutil.parser.parse(page.created_at).strftime(DATE_TEMPLATE) if \
                hasattr(page, "created_at") else ""
            # Date last updated
            page_view.last_updated_date = dateutil.parser.parse(page.updated_at).strftime(DATE_TEMPLATE) if \
                hasattr(page, "updated_at") else ""

            page_views.append(page_view)
    except Exception as e:
        print("Skipping page download that gave the following error:")
        print(e)

    return page_views


def findCourseAssignments(course):
    assignment_views = []

    # Get all assignments
    assignments = course.get_assignments()

    try:
        for assignment in assignments:
            # Create a new assignment view
            assignment_view = assignmentView()

            # ID
            assignment_view.id = assignment.id if \
                hasattr(assignment, "id") else ""

            # Title
            assignment_view.title = makeValidFilename(str(assignment.name)) if \
                hasattr(assignment, "name") else ""
            # Description
            assignment_view.description = str(assignment.description) if \
                hasattr(assignment, "description") else ""

            # Assigned date
            assignment_view.assigned_date = assignment.created_at_date.strftime(DATE_TEMPLATE) if \
                hasattr(assignment, "created_at_date") else ""
            # Due date
            assignment_view.due_date = assignment.due_at_date.strftime(DATE_TEMPLATE) if \
                hasattr(assignment, "due_at_date") else ""

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
                try:  # Download all submissions for entire class
                    submissions = assignment.get_submissions()
                    submissions[0]  # Trigger Unauthorized if not allowed
                except Unauthorized:
                    print("Not authorized to download entire class submissions for this assignment")
                    # Download submission for this user only
                    submissions = [assignment.get_submission(USER_ID)]
                submissions[0]  # throw error if no submissions found at all but without error
            except (ResourceDoesNotExist, NameError, IndexError):
                print('Got no submissions from either class or user: {}'.format(USER_ID))
            except Exception as e:
                print("Failed to retrieve submissions for this assignment")
                print(e.__class__.__name__)
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
                            print('No attachments')
                        else:
                            for attachment in submission.attachments:
                                attach_view = attachmentView()
                                attach_view.url = attachment["url"]
                                attach_view.id = attachment["id"]
                                attach_view.filename = attachment["filename"]
                                sub_view.attachments.append(attach_view)
                        assignment_view.submissions.append(sub_view)
                except Exception as e:
                    print("Skipping submission that gave the following error:")
                    print(e)

            assignment_views.append(assignment_view)
    except Exception as e:
        print("Skipping course assignments that gave the following error:")
        print(e)

    return assignment_views


def findCourseAnnouncements(course):
    announcement_views = []

    try:
        announcements = course.get_discussion_topics(only_announcements=True)

        for announcement in announcements:
            discussion_view = getDiscussionView(announcement)

            announcement_views.append(discussion_view)
    except Exception as e:
        print("Skipping announcement that gave the following error:")
        print(e)

    return announcement_views


def getDiscussionView(discussion_topic):
    # Create discussion view
    discussion_view = discussionView()

    # ID
    discussion_view.id = discussion_topic.id if hasattr(discussion_topic, "id") else 0

    # Title
    discussion_view.title = str(discussion_topic.title) if hasattr(discussion_topic, "title") else ""
    # Author
    discussion_view.author = str(discussion_topic.user_name) if hasattr(discussion_topic, "user_name") else ""
    # Posted date
    discussion_view.posted_date = discussion_topic.created_at_date.strftime("%B %d, %Y %I:%M %p") if hasattr(
        discussion_topic, "created_at_date") else ""
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
                topic_entry_view.posted_date = topic_entry.created_at_date.strftime("%B %d, %Y %I:%M %p") if hasattr(
                    topic_entry, "created_at_date") else ""
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
                        topic_reply_view.author = str(topic_reply.user_name) if hasattr(topic_reply,
                                                                                        "user_name") else ""
                        # Posted Date
                        topic_reply_view.posted_date = topic_reply.created_at_date.strftime(
                            "%B %d, %Y %I:%M %p") if hasattr(topic_reply, "created_at_date") else ""
                        # Body
                        topic_reply_view.message = str(topic_reply.message) if hasattr(topic_reply, "message") else ""

                        topic_entry_view.topic_replies.append(topic_reply_view)
                except Exception as e:
                    print("Tried to enumerate discussion topic entry replies but received the following error:")
                    print(e)

                discussion_view.topic_entries.append(topic_entry_view)
        except Exception as e:
            print("Tried to enumerate discussion topic entries but received the following error:")
            print(e)

    # Amount of pages
    discussion_view.amount_pages = int(
        topic_entries_counter / 50) + 1  # Typically 50 topic entries are stored on a page before it creates another page.

    return discussion_view


def findCourseDiscussions(course):
    discussion_views = []

    try:
        discussion_topics = course.get_discussion_topics()

        for discussion_topic in discussion_topics:
            discussion_view = None
            discussion_view = getDiscussionView(discussion_topic)

            discussion_views.append(discussion_view)
    except Exception as e:
        print("Skipping discussion that gave the following error:")
        print(e)

    return discussion_views


def getCourseView(course):
    course_view = courseView()

    # Course ID
    course_view.course_id = course.id if hasattr(course, "id") else 0

    # Course term
    course_view.term = makeValidFilename(
        course.term["name"] if hasattr(course, "term") and "name" in course.term.keys() else "")

    # Course code
    course_view.course_code = makeValidFilename(course.course_code if hasattr(course, "course_code") else "")

    # Course name
    course_view.name = course.name if hasattr(course, "name") else ""

    print("Working on " + course_view.term + ": " + course_view.name)

    # Course assignments
    print("  Getting assignments")
    course_view.assignments = findCourseAssignments(course)

    # Course announcements
    print("  Getting announcements")
    course_view.announcements = findCourseAnnouncements(course)

    # Course discussions
    print("  Getting discussions")
    course_view.discussions = findCourseDiscussions(course)

    # Course pages
    print("  Getting pages")
    course_view.pages = findCoursePages(course)

    return course_view


def exportAllCourseData(course_view):
    json_str = json.dumps(json.loads(jsonpickle.encode(course_view, unpicklable=False)), indent=4)

    course_output_dir = os.path.join(DL_LOCATION, course_view.term,
                                     course_view.course_code)

    # Create directory if not present
    if not os.path.exists(course_output_dir):
        os.makedirs(course_output_dir)

    course_output_path = os.path.join(course_output_dir,
                                      course_view.course_code + ".json")

    with open(course_output_path, "w") as out_file:
        out_file.write(json_str)
    flag_file_if_needed(course_output_path)


def downloadCourseHTML(api_url, cookies_path):
    if (cookies_path == ""):
        return

    course_dir = DL_LOCATION

    if not os.path.exists(course_dir):
        os.makedirs(course_dir)

    course_list_path = os.path.join(course_dir, "course_list.html")

    # Downloads the course list.
    if not os.path.exists(course_list_path):
        download_page(api_url + "/courses/", cookies_path, course_dir, "course_list.html")
        flag_file_if_needed(course_list_path)


def downloadCourseHomePageHTML(api_url, course_view, cookies_path):
    if (cookies_path == ""):
        return

    dl_dir = os.path.join(DL_LOCATION, course_view.term,
                          course_view.course_code)

    # Create directory if not present
    if not os.path.exists(dl_dir):
        os.makedirs(dl_dir)

    homepage_path = os.path.join(dl_dir, "homepage.html")

    # Downloads the course home page.
    if not os.path.exists(homepage_path):
        download_page(api_url + "/courses/" + str(course_view.course_id), cookies_path, dl_dir, "homepage.html")
        flag_file_if_needed(homepage_path)


def downloadAssignmentPages(api_url, course_view, cookies_path):
    if (cookies_path == "" or len(course_view.assignments) == 0):
        return

    base_assign_dir = os.path.join(DL_LOCATION, course_view.term,
                                   course_view.course_code, "assignments")

    # Create directory if not present
    if not os.path.exists(base_assign_dir):
        os.makedirs(base_assign_dir)

    assignment_list_path = os.path.join(base_assign_dir, "assignment_list.html")

    # Download assignment list (theres a chance this might be the course homepage if the course has the assignments page disabled)
    if not os.path.exists(assignment_list_path):
        download_page(api_url + "/courses/" + str(course_view.course_id) + "/assignments/", cookies_path,
                      base_assign_dir, "assignment_list.html")

    for assignment in course_view.assignments:
        assignment_title = makeValidFilename(str(assignment.title))
        assignment_title = shortenFileName(assignment_title, len(assignment_title) - MAX_FOLDER_NAME_SIZE)
        assign_dir = os.path.join(base_assign_dir, assignment_title)

        # Download an html image of each assignment (includes assignment instructions and other stuff).
        # Currently, this will only download the main assignment page and not external pages, this is
        # because these external pages are given in a json format. Saving these would require a lot
        # more work then normal.
        if assignment.html_url != "":
            if not os.path.exists(assign_dir):
                os.makedirs(assign_dir)

            assignment_page_path = os.path.join(assign_dir, "assignment.html")

            # Download assignment page, this usually has instructions and etc.
            if not os.path.exists(assignment_page_path):
                download_page(assignment.html_url, cookies_path, assign_dir, "assignment.html")

        for submission in assignment.submissions:
            submission_dir = assign_dir

            # If theres more then 1 submission, add unique id to download dir
            if len(assignment.submissions) != 1:
                submission_dir = os.path.join(assign_dir, str(submission.user_id))

            if submission.preview_url != "":
                if not os.path.exists(submission_dir):
                    os.makedirs(submission_dir)

                submission_page_dir = os.path.join(submission_dir, "submission.html")

                # Download submission url, this is typically a more focused page
                if not os.path.exists(submission_page_dir):
                    download_page(submission.preview_url, cookies_path, submission_dir, "submission.html")

                    # If theres more then 1 attempt, save each attempt in attempts folder
            if (submission.attempt != 1 and assignment.updated_url != "" and assignment.html_url != ""
                    and assignment.html_url.rstrip("/") != assignment.updated_url.rstrip("/")):
                submission_dir = os.path.join(assign_dir, "attempts")

                if not os.path.exists(submission_dir):
                    os.makedirs(submission_dir)

                # Saves the attempts if multiple were taken, doesn't account for
                # different ID's however, as I wasnt able to find out what the url
                # for the specific id's attempts would be.
                for i in range(submission.attempt):
                    filename = "attempt_" + str(i + 1) + ".html"
                    submission_page_attempt_dir = os.path.join(submission_dir, filename)

                    if not os.path.exists(submission_page_attempt_dir):
                        download_page(assignment.updated_url + "/history?version=" + str(i + 1), cookies_path,
                                      submission_dir, filename)


def downloadCourseModulePages(api_url, course_view, cookies_path):
    if (cookies_path == "" or len(course_view.modules) == 0):
        return

    modules_dir = os.path.join(DL_LOCATION, course_view.term,
                               course_view.course_code, "modules")

    # Create modules directory if not present
    if not os.path.exists(modules_dir):
        os.makedirs(modules_dir)

    module_list_dir = os.path.join(modules_dir, "modules_list.html")

    # Downloads the modules page (possible this is disabled by the teacher)
    if not os.path.exists(module_list_dir):
        download_page(api_url + "/courses/" + str(course_view.course_id) + "/modules/", COOKIES_PATH, modules_dir,
                      "modules_list.html")

    for module in course_view.modules:
        for item in module.items:
            # If problems arise due to long pathnames, changing module.name to module.id might help, this can also be done with item.title
            # A change would also have to be made in findCourseModules(course, course_view)
            module_name = makeValidFilename(str(module.name))
            module_name = shortenFileName(module_name, len(module_name) - MAX_FOLDER_NAME_SIZE)
            items_dir = os.path.join(modules_dir, module_name)

            # Create modules directory if not present
            if item.url != "":
                if not os.path.exists(items_dir):
                    os.makedirs(items_dir)

                filename = makeValidFilename(str(item.title)) + ".html"
                module_item_dir = os.path.join(items_dir, filename)

                # Download the module page.
                if not os.path.exists(module_item_dir):
                    download_page(item.url, cookies_path, items_dir, filename)
                    # flag_file_if_needed(flag_file_if_needed(download_page(item.url, cookies_path, items_dir, filename)))


def downloadCourseAnnouncementPages(api_url, course_view, cookies_path):
    if (cookies_path == "" or len(course_view.announcements) == 0):
        return

    base_announce_dir = os.path.join(DL_LOCATION, course_view.term,
                                     course_view.course_code, "announcements")

    # Create directory if not present
    if not os.path.exists(base_announce_dir):
        os.makedirs(base_announce_dir)

    announcement_list_dir = os.path.join(base_announce_dir, "announcement_list.html")

    # Download assignment list (theres a chance this might be the course homepage if the course has the assignments page disabled)
    if not os.path.exists(announcement_list_dir):
        download_page(api_url + "/courses/" + str(course_view.course_id) + "/announcements/", cookies_path,
                      base_announce_dir, "announcement_list.html")

    for announcements in course_view.announcements:
        announcements_title = makeValidFilename(str(announcements.title))
        announcements_title = shortenFileName(announcements_title, len(announcements_title) - MAX_FOLDER_NAME_SIZE)
        announce_dir = os.path.join(base_announce_dir, announcements_title)

        if announcements.url == "":
            continue

        if not os.path.exists(announce_dir):
            os.makedirs(announce_dir)

        # Downloads each page that a discussion takes.
        for i in range(announcements.amount_pages):
            filename = "announcement_" + str(i + 1) + ".html"
            announcement_page_dir = os.path.join(announce_dir, filename)

            # Download assignment page, this usually has instructions and etc.
            if not os.path.exists(announcement_page_dir):
                download_page(announcements.url + "/page-" + str(i+1), cookies_path, announce_dir, filename)
                # flag_file_if_needed(download_page)

def downloadCourseDiscussionPages(api_url, course_view, cookies_path):
    if (cookies_path == "" or len(course_view.discussions) == 0):
        return

    base_discussion_dir = os.path.join(DL_LOCATION, course_view.term,
                                       course_view.course_code, "discussions")

    # Create directory if not present
    if not os.path.exists(base_discussion_dir):
        os.makedirs(base_discussion_dir)

    discussion_list_dir = os.path.join(base_discussion_dir, "discussion_list.html")

    # Download assignment list (theres a chance this might be the course homepage if the course has the assignments page disabled)
    if not os.path.exists(discussion_list_dir):
        download_page(api_url + "/courses/" + str(course_view.course_id) + "/discussion_topics/", cookies_path,
                      base_discussion_dir, "discussion_list.html")

    for discussion in course_view.discussions:
        discussion_title = makeValidFilename(str(discussion.title))
        discussion_title = shortenFileName(discussion_title, len(discussion_title) - MAX_FOLDER_NAME_SIZE)
        discussion_dir = os.path.join(base_discussion_dir, discussion_title)

        if discussion.url == "":
            continue

        if not os.path.exists(discussion_dir):
            os.makedirs(discussion_dir)

        # Downloads each page that a discussion takes.
        for i in range(discussion.amount_pages):
            filename = "discussion_" + str(i + 1) + ".html"
            discussion_page_dir = os.path.join(discussion_dir, filename)

            # Download assignment page, this usually has instructions and etc.
            if not os.path.exists(discussion_page_dir):
                download_page(discussion.url + "/page-" + str(i+1), cookies_path, discussion_dir, filename)
                # flag_file_if_needed(download_page)

# Function to load JSON data from a file
def loadJsonFile(file_path):
    try:
        with open(file_path, 'r') as file:
            data = json.load(file)
        return data
    except FileNotFoundError:
        return None

# Function to sort JSON data by a specified key
def sortJsonData(data, key):
    if isinstance(data, list):
        return sorted(data, key=lambda x: x.get(key, ''))
    else:
        return data

# Function to save sorted data to a JSON file
def saveSortedJsonToFile(data, file_path):
    with open(file_path, 'w+') as file:
        json.dump(data, file, indent=4)


# Redirects stdout to Text widget
class RedirectText:
    def __init__(self, text_widget):
        self.text_widget = text_widget


def write(self, text):
    # Insert text into the text widget
    self.text_widget.insert("end", text)

    # Write to console
    sys.__stdout__.write(text)

# Validation function to check if the required GUI entries are empty
def validate_entry():
    canvas_url = canvas_url_entry.get()
    api_key = api_key_entry.get()
    user_id = user_id_entry.get()

    if not canvas_url:
        messagebox.showerror("Error", "Canvas URL is required")
        return False
    if not api_key:
        messagebox.showerror("Error", "API Key is required")
        return False
    if not user_id:
        messagebox.showerror("Error", "User ID is required")
        return False
    
    return True

def browse_folder():
    folder_path = filedialog.askdirectory()
    output_folder_entry.delete(0, tk.END)
    output_folder_entry.insert(0, folder_path)

# Initializes the database connection
def initDatabase():
   
    mydb = mysql.connector.connect(
        host="localhost",
        user="root",
        passwd="root",
        database="CPSTOPS"
    )

    return mydb

# Initializes the cursor element 
def initCursor(mydb):
    mycursor = mydb.cursor()

    return mycursor

# Creates entry in the database with course information
def addDBCourse(cview,db,cursor):

    id = cview.id
    name = cview.name
    start_at = cview.start_at
    end_at = cview.end_at

    #print(term, " THIS IS THE TERM IDK WHAT THAT IS ")

    cursor.execute("INSERT INTO courses (courseID, name, start_at, end_at) VALUES (%s, %s, %s, %s)", (id,name,end_at,start_at))
    db.commit()

    return

# Create Credentials table
def createCredentialsTable(db, cursor):
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS user_credentials (user_id int NOT NULL, api_url varchar(255), api_key varchar(255), cookies_path varchar(255), dl_location varchar(255))")
    db.commit()

# Retrieve single user data by user ID
def getCredentialData(cursor, user_id):
    cursor.execute("SELECT * FROM user_credentials WHERE user_id = %s", (user_id,))
    userCreds = cursor.fetchone()
    print("Credentials loaded from table:")
    print(userCreds)


if __name__ == "__main__":
    # Create a GUI window
    root = tk.Tk()
    root.geometry("900x700")
    root.title("Canvas Student Data Export Tool")
    font = ("Helvetica", 22)
    label_font = ("Helvetica", 24, "bold")

    # Create and place GUI elements
    canvas_url_label = tk.Label(root, text="Canvas Base URL:", font=label_font)
    canvas_url_label.pack()
    canvas_url_entry = tk.Entry(root, font=font)
    canvas_url_entry.pack()

    api_key_label = tk.Label(root, text="API Key:", font=label_font)
    api_key_label.pack()
    api_key_entry = tk.Entry(root, font=font)
    api_key_entry.pack()

    user_id_label = tk.Label(root, text="Canvas User ID:", font=label_font)
    user_id_label.pack()
    user_id_entry = tk.Entry(root, font=font)
    user_id_entry.pack()

    cookies_path_label = tk.Label(root, text="Cookies Path (optional):", font=label_font)
    cookies_path_label.pack()
    cookies_path_entry = tk.Entry(root, font=font)
    cookies_path_entry.pack()

    output_folder_label = tk.Label(root, text="Output Folder:", font=label_font)
    output_folder_label.pack()
    output_folder_entry = tk.Entry(root, font=font)
    output_folder_entry.pack()

    def export_data():
        global API_URL
        global API_KEY
        global USER_ID
        global COOKIES_PATH
        global DL_LOCATION
        
        API_URL = canvas_url_entry.get()
        API_KEY = api_key_entry.get()
        USER_ID = user_id_entry.get()
        COOKIES_PATH = cookies_path_entry.get()
        if output_folder_entry.get() != "":
            DL_LOCATION = output_folder_entry.get()

        #Remove entry widgets
        for widget in root.winfo_children():
            widget.destroy()

        # Create a progress bar widget based on course number
        progress_label = tk.Label(root, text="Canvas Export Progress:", font=label_font)
        progress_label.pack(pady = 20)
        progress_var = tk.DoubleVar()
        progress_bar = Progressbar(root, length=700, mode="determinate", variable=progress_var)
        progress_bar.pack()

        # Text widget to display stdout print statements
        console_text = scrolledtext.ScrolledText(root, wrap=tk.WORD)
        console_text.pack(pady = 20)

        # Initialize Database Connection
        dbInit = initDatabase()
        print("Database connection initialized.\n")

        # Initialize Database Cursor
        cursInit = initCursor(dbInit)

        # Create tables
        createCredentialsTable(dbInit, cursInit)
        print("Credentials table created.\n")

        # Call the function with the user ID
        user_id = USER_ID
        getCredentialData(cursInit, user_id)


        # Redirect stdout to the text widget (Print statements will still show in console)
        # sys.stdout = RedirectText(console_text)

        print("Welcome to the Canvas Student Data Export Tool\n")

        print("API_URL:", API_URL)
        print("API_KEY:", API_KEY)
        print("USER_ID:", USER_ID)
        print("DL_LOCATION:", DL_LOCATION)

        print("\nConnecting to canvas\n")

        # Initialize a new Canvas object
        canvas = Canvas(API_URL, API_KEY)


        print("Creating output directory: " + DL_LOCATION + "\n")
        # Create directory if not present
        if not os.path.exists(DL_LOCATION):
            os.makedirs(DL_LOCATION)

        all_courses_views = []

        print("Getting list of all courses\n")
        courses = canvas.get_courses(include="term")

        skip = set(COURSES_TO_SKIP)

        if (COOKIES_PATH):
            print("  Downloading course list page")
            downloadCourseHTML(API_URL, COOKIES_PATH)

        total_courses = 0
        #calculate how many total courses of Paginated List 
        for course in courses: 
            total_courses += 1
    
        course_index = 0
        for course in courses:
            # Simulate a progress bar update
            progress_percentage = (course_index / total_courses * 100)
            progress_var.set(progress_percentage)
            root.update_idletasks()
       
            if course.id in skip or not hasattr(course, "name") or not hasattr(course, "term"):
                continue

            course_view = getCourseView(course)

            all_courses_views.append(course_view)

            print("  Downloading all files")
            downloadCourseFiles(course, course_view)

            print("  Downloading submission attachments")
            download_submission_attachments(course, course_view)

            print("  Getting modules and downloading module files")
            course_view.modules = findCourseModules(course, course_view)


            if(COOKIES_PATH):
                print("  Downloading course home page")
                downloadCourseHomePageHTML(API_URL, course_view, COOKIES_PATH)

                print("  Downloading assignment pages")
                downloadAssignmentPages(API_URL, course_view, COOKIES_PATH)

                print("  Downloading course module pages")
                downloadCourseModulePages(API_URL, course_view, COOKIES_PATH)

                print("  Downloading course announcements pages")
                downloadCourseAnnouncementPages(API_URL, course_view, COOKIES_PATH)   

                print("  Downloading course discussion pages")
                downloadCourseDiscussionPages(API_URL, course_view, COOKIES_PATH)

            # Add course entry to database
            addDBCourse(course,dbInit,cursInit)

            print("  Exporting all course data")
            exportAllCourseData(course_view)
            course_index += 1

        print("Exporting data from all courses combined as one file: "
            "all_output.json")
        # Awful hack to make the JSON pretty. Decode it with Python stdlib json
        # module then re-encode with indentation
        json_str = json.dumps(json.loads(jsonpickle.encode(all_courses_views,
                                                        unpicklable=False)),
                            indent=4)

        all_output_path = os.path.join(DL_LOCATION, "all_output.json")

        with open(all_output_path, "w") as out_file:
            out_file.write(json_str)

        print("\nProcess complete. All canvas data exported!")
        messagebox.showinfo("Success", "Data export completed!")
        completion_label = tk.Label(root, text="Canvas Export Complete!", font=label_font)
        completion_label.pack(pady = 20)

        
        input_file = 'output/all_output.json'
        output_file = 'output/sorted_output.json'

        # Ask the user what to sort by:
        print("Would you like to sort the final output?")
        print("Sort options: course_code, course_id, name, term")
        sort_key = input(
            "Enter a valid sort type: (leave blank to skip sort) ")  # Replace with the key by which you want to sort

        if sort_key == '':
            print("Skipping sort.")
            exit()

        # Load data from the input JSON file
        data = loadJsonFile(input_file)

        if data is not None:
            # Sort the data by the specified key
            sorted_data = sortJsonData(data, sort_key)

            # Save the sorted data to the output JSON file
            saveSortedJsonToFile(sorted_data, output_file)

            print(f"Data sorted by '{sort_key}' and saved to '{output_file}'.")
        else:
            print(f"File '{input_file}' not found or empty.")

        # ====================================================
        # Close the database connection?????



    def export_button_click():
        # Keep prompting the user for input until all fields are filled correctly
        if (validate_entry()):
            export_thread = threading.Thread(target=export_data)
            export_thread.start()  # Proceed with exporting data in seperate thread once all fields are filled correctly

    browse_button = tk.Button(root, text="Browse", font = font, command=browse_folder)
    browse_button.pack(pady = 20)

    export_button = tk.Button(root, text="Export Data", font = font, command=export_button_click)
    export_button.pack(pady = 20)

# Run the GUI main loop
root.mainloop()
