from subprocess import CalledProcessError, run
import os
import platform
import shutil

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

def download_page(url, cookies_path, output_path, output_name_template = "", additional_args = ()):
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
        print(cmd)
        proc = run(cmd, shell=True, check=True, capture_output=True)
        if stdout := proc.stdout.strip():
            print(stdout)
        if stderr := proc.stderr.strip():
            raise CalledProcessError(proc.returncode, proc.args, output=stdout, stderr=stderr)
    except Exception as e:
        print(f"Was not able to save the URL {url} using singlefile. The reported error was:", e)

#if __name__ == "__main__":
    #download_page("https://www.google.com/", "", "./output/test", "test.html")
