from subprocess import CalledProcessError, run
import os
import platform
import shutil
import time

if platform.system() == "Windows":
    SINGLEFILE_BINARY_PATH = os.path.join("node_modules", ".bin", "single-file.cmd")
else:
    SINGLEFILE_BINARY_PATH = os.path.join("node_modules", ".bin", "single-file")

# Prefer calling the Node entry directly for reliable cross-platform arg passing
SINGLEFILE_NODE_ENTRY = os.path.join("node_modules", "single-file-cli", "single-file-node.js")

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


# Default timeout in seconds for SingleFile to complete. Can be overridden.
SINGLEFILE_TIMEOUT = 60.0  # 1 minute


def override_chrome_path(path: str):
    """Allow callers to override the detected Chrome path at runtime."""
    global CHROME_PATH
    CHROME_PATH = path.strip()


def override_singlefile_timeout(timeout: float):
    """Allow callers to override the SingleFile timeout at runtime."""
    global SINGLEFILE_TIMEOUT
    if timeout > 0:
        SINGLEFILE_TIMEOUT = timeout


def addQuotes(str):
    return "\"" + str.strip("\"") + "\""


def download_page(url, cookies_path, output_path, output_name_template = "", additional_args = (), verbose=False):
    # Build full output path we expect SingleFile to create
    expected_output = os.path.join(output_path, output_name_template) if output_name_template else output_path

    # Prepare argument list for robust cross-platform execution
    node_path = shutil.which("node")
    use_shell_string = False

    # Convert timeout to milliseconds for SingleFile CLI argument
    timeout_ms = str(int(SINGLEFILE_TIMEOUT * 1000))

    if node_path and os.path.exists(SINGLEFILE_NODE_ENTRY):
        cmd_args = [
            node_path,
            SINGLEFILE_NODE_ENTRY,
            url,
            expected_output,
            "--filename-conflict-action=overwrite",
            "--browser-capture-max-time=" + timeout_ms,
        ]
        if CHROME_PATH:
            cmd_args.append("--browser-executable-path=" + CHROME_PATH.strip("\""))
        if cookies_path:
            cmd_args.append("--browser-cookies-file=" + cookies_path)
        # Append any additional CLI args as-is
        cmd_args.extend(list(additional_args))
    else:
        # Fallback to the shim in node_modules/.bin using a shell command
        use_shell_string = True
        args = [
            addQuotes(SINGLEFILE_BINARY_PATH),
            addQuotes(url),
            addQuotes(expected_output),
            "--filename-conflict-action=overwrite",
            "--browser-capture-max-time=" + timeout_ms,
        ]
        if CHROME_PATH:
            args.append("--browser-executable-path=" + addQuotes(CHROME_PATH.strip("\"")))
        if cookies_path:
            args.append("--browser-cookies-file=" + addQuotes(cookies_path))
        args.extend(additional_args)
        cmd_args = " ".join(args)

    try:
        if verbose:
            if isinstance(cmd_args, list):
                print(f"    Executing: {' '.join(cmd_args)}")
            else:
                print(f"    Executing: {cmd_args}")

        proc = run(cmd_args, shell=use_shell_string, check=True, capture_output=True)

        # Decode outputs immediately so we can surface them even if the file check fails
        stdout_text = proc.stdout.decode("utf-8", errors="replace").strip()
        stderr_text = proc.stderr.decode("utf-8", errors="replace").strip()

        # Optionally show SingleFile logs right after the process exits
        if verbose:
            if stdout_text:
                print(stdout_text)
            if stderr_text:
                # SingleFile prints non-error info to stderr; show only in verbose mode
                print(stderr_text)

        # Wait for the file to exist and be readable (handles Windows write/lock delays)
        start_time = time.monotonic()
        deadline = start_time + SINGLEFILE_TIMEOUT + 5.0  # seconds, add buffer
        delay = 0.1
        while True:
            try:
                if not os.path.exists(expected_output):
                    raise FileNotFoundError(expected_output)
                with open(expected_output, "r", encoding="utf-8") as f:
                    content = f.read()

                # Detect login page content
                login_indicators = [
                    "<title>Log in to Canvas</title>",
                    'id="new_login_data"',
                    'autocomplete="current-password"',
                ]
                if any(indicator in content for indicator in login_indicators):
                    # Clean up the invalid file
                    try:
                        os.remove(expected_output)
                    except Exception:
                        pass
                    raise Exception("Authentication failed, downloaded a login page. Please update your cookies.")

                break  # success
            except (PermissionError, FileNotFoundError) as e:
                now = time.monotonic()
                if now >= deadline:
                    # Enrich the error with SingleFile logs for better diagnostics
                    elapsed = now - start_time
                    details = [
                        f"SingleFile produced no readable output within {elapsed:.1f}s",
                        f"URL: {url}",
                        f"Expected path: {expected_output}",
                        f"Exit code: {proc.returncode}",
                    ]
                    if stdout_text:
                        details.append(f"stdout:\n{stdout_text}")
                    if stderr_text:
                        details.append(f"stderr:\n{stderr_text}")
                    raise Exception("\n".join(details)) from e
                time.sleep(min(delay, deadline - now))
                delay = min(delay * 1.5, 1.0)

    except CalledProcessError as e:
        # Re-raise with more context including both stdout and stderr
        stderr_text = ""
        stdout_text = ""
        try:
            stderr_text = e.stderr.decode('utf-8', errors='replace') if e.stderr is not None else ""
        except Exception:
            pass
        try:
            stdout_text = e.stdout.decode('utf-8', errors='replace') if e.stdout is not None else ""
        except Exception:
            pass
        msg_parts = [f"SingleFile failed for {url}."]
        if stdout_text:
            msg_parts.append(f"stdout:\n{stdout_text}")
        if stderr_text:
            msg_parts.append(f"stderr:\n{stderr_text}")
        raise Exception("\n".join(msg_parts)) from e
    except Exception as e:
        # Propagate our own exceptions
        raise e

#if __name__ == "__main__":
    #download_page("https://www.google.com/", "", "./output/test", "test.html")
