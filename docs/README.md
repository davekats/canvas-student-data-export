# Introduction
The Canvas Student Data Export Tool can export nearly all of a student's data from Instructure Canvas Learning Management System (Canvas LMS).  
This is useful when you are graduating or leaving your college or university, and would like to have a backup of all the data you had in canvas.  

The tool exports all of the following data:  
- Course Assignments
- Course Announcements
- Course Discussions
- Course Pages
- Course Files
- Course Modules

The tool will export your data in JSON format, and will organize it nicely into folders named for every term of every year.  
Example:  
- Fall 2013
  - Econ 101
    - files
    - modules
    - Econ 101.json
  - English 101
    - files
    - modules
    - English 101.json
- Fall 2014
- Fall 2015
- Fall 2016
- Spring 2014
- Spring 2015
- Spring 2016
- Spring 2017
- Winter 2014
- Winter 2015
- Winter 2016
- Winter 2017
- all_output.json

# Getting Started
## Dependencies
To run the program, you will need the following dependencies:  
`pip install requests`  
`pip install jsonpickle`  
`pip install canvasapi` 
`pip install python-dateutil`

You can install these dependencies using
`pip install -r requirements.txt`

Then run from the command line:  
`python export.py`

## Configuration
These are the configuration parameters for the program:
- Canvas API URL
- Canvas API key
- Canvas User ID
- Directory in which to download course information to (will be created if not present)
- List of Course IDs that should be skipped

# Contribute
I would love to see this script's functionality expanded and improved! I welcome all pull requests :) Thank you!  
