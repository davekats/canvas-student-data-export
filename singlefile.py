from subprocess import CalledProcessError, run
import os
import platform
import shutil
import time

if platform.system() == "Windows":
    SINGLEFILE_BINARY_PATH = os.path.join("node_modules", ".bin", "single-file.cmd")
else:
    SINGLEFILE_BINARY_PATH = os.path.join("node_modules", ".bin", "single-file")

# Default Chrome/Chromium executable path is determined heuristically per-OS.


def _detect_chrome_path() -> str:
    """Return a best-guess path to a Chrome/Chromium executable for the current OS."""
    system = platform.system().lower()

    candidates = []

    if system == "windows":
        candidates = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files\Chromium\Application\chrome.exe",
        ]
    elif system == "darwin":  # macOS
        candidates = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
            "/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary",
        ]
    else:  # assume Linux/Unix
        for name in ["google-chrome", "google-chrome-stable", "chromium-browser", "chromium", "chrome"]:
            path = shutil.which(name)
            if path:
                return path

    for path in candidates:
        if os.path.exists(path):
            return path

    # Fallback – rely on SingleFile auto-detect; returns empty string
    return ""


# Mutable global – can be overridden at runtime by export.py
CHROME_PATH = _detect_chrome_path()


def override_chrome_path(path: str):
    """Allow callers to override the detected Chrome path at runtime."""
    global CHROME_PATH
    CHROME_PATH = path.strip()

def addQuotes(str):
    return "\"" + str.strip("\"") + "\""

def download_page(url, cookies_path, output_path, output_name_template = "", additional_args = (), verbose=False):
    args = [
        addQuotes(SINGLEFILE_BINARY_PATH),
    ]

    if CHROME_PATH:
        args.append("--browser-executable-path=" + addQuotes(CHROME_PATH.strip("\"")))

    args.extend([
        "--browser-cookies-file=" + addQuotes(cookies_path),
        "--output-directory=" + addQuotes(output_path),
        addQuotes(url),
    ])

    if(output_name_template != ""):
        args.append("--filename-template=" + addQuotes(output_name_template))

    args.extend(additional_args)

    try:
        cmd = " ".join(args)
        if verbose:
            print(f"    Executing: {cmd}")
        
        proc = run(cmd, shell=True, check=True, capture_output=True)
        
        # Check if the downloaded page is a login page
        # Retry logic to handle file locking race condition on Windows
        max_retries = 3
        retry_delay = 0.1 # seconds
        for attempt in range(max_retries):
            try:
                with open(os.path.join(output_path, output_name_template), "r", encoding="utf-8") as f:
                    content = f.read()
                
                # More robust login page detection logic
                login_indicators = [
                    "<title>Log in to Canvas</title>",
                    'id="new_login_data"',
                    'autocomplete="current-password"',
                ]

                if any(indicator in content for indicator in login_indicators):
                    # Clean up the invalid file
                    os.remove(os.path.join(output_path, output_name_template))
                    raise Exception("Authentication failed, downloaded a login page. Please update your cookies.")
                
                # If we succeed, break the loop
                break 
            except PermissionError:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    # Re-raise the exception on the last attempt
                    raise

        if verbose:
            if stdout := proc.stdout.strip():
                    print(stdout)
            if stderr := proc.stderr.strip():
                # Single-file puts non-error info in stderr, so only show in verbose
                print(stderr)

    except CalledProcessError as e:
        # Re-raise with more context
        raise Exception(f"SingleFile failed for {url}. Stderr: {e.stderr.decode('utf-8')}") from e
    except Exception as e:
        # Catch our login page exception or others
        raise e

#if __name__ == "__main__":
    #download_page("https://www.google.com/", "", "./output/test", "test.html")
