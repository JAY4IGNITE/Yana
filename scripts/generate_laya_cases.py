"""Generate versioned evaluation dataset for YANA Laya routing.

Generates 540 diverse examples covering 10 distinct categories (54 per category):
1. ordinary_chat
2. exact_command
3. compound_command
4. negated_command
5. quoted_command
6. ambiguous
7. failure_related
8. code_terminal
9. browser
10. files
"""

import hashlib
import json
import random
from pathlib import Path
from typing import Any, Dict, List

SEED = 42
random.seed(SEED)

OUTPUT_DIR = Path("apps/agent/evals/laya")
CASES_FILE = OUTPUT_DIR / "cases.jsonl"
MANIFEST_FILE = OUTPUT_DIR / "manifest.json"


def get_ordinary_chat_cases() -> List[Dict[str, Any]]:
    cases = []
    topics = [
        ("What is the capital of {}", ["France", "Japan", "Brazil", "Canada", "Australia", "Germany", "India", "Egypt", "Spain", "Norway"]),
        ("Can you tell me a short joke about {}?", ["programmers", "coffee", "cats", "space travel", "musicians", "chemists", "robots", "airplanes"]),
        ("How does {} work in simple terms?", ["photosynthesis", "gravity", "blockchain", "DNS resolution", "machine learning", "cellular mitosis", "vaccination", "compiler optimization"]),
        ("Who wrote the novel {}?", ["1984", "Pride and Prejudice", "Dune", "To Kill a Mockingbird", "The Hobbit", "Crime and Punishment", "Frankenstein", "Moby Dick"]),
        ("Explain the difference between {} and {}.", [
            ("SQL", "NoSQL"), ("HTTP", "HTTPS"), ("compiler", "interpreter"), ("TCP", "UDP"),
            ("process", "thread"), ("stack", "heap"), ("synchronous", "asynchronous"), ("RAM", "ROM")
        ]),
        ("What are three effective habits for better {}?", ["sleep", "public speaking", "typing speed", "time management", "mental focus", "productivity"]),
        ("Can you write a polite thank-you message for {}?", ["a job interview", "a dinner party", "a birthday gift", "a helpful recommendation", "mentorship", "a project collaboration"]),
    ]
    for tmpl, vals in topics:
        for val in vals:
            if isinstance(val, tuple):
                text = tmpl.format(val[0], val[1])
            else:
                text = tmpl.format(val)
            cases.append({
                "text": text,
                "category": "ordinary_chat",
                "expected_domain": "conversation",
                "expected_reasoning_tier": "routine",
                "mode": "chat",
                "is_exact_command": False,
            })
            if len(cases) >= 54:
                break
        if len(cases) >= 54:
            break
    return cases[:54]


def get_exact_command_cases() -> List[Dict[str, Any]]:
    # Exact supported commands from RuleBasedPlanner:
    # 'show system info', 'take a screenshot', 'open app <app>', 'read file "<path>"'
    apps = [
        "notepad.exe", "calc.exe", "mspaint.exe", "cmd.exe", "powershell.exe",
        "explorer.exe", "taskmgr.exe", "regedit.exe", "write.exe", "charmap.exe",
        "cleanmgr.exe", "magnify.exe", "snippingtool.exe", "control.exe", "services.msc",
        "msinfo32.exe", "perfmon.exe", "compmgmt.msc"
    ]
    files = [
        r"C:\Users\ramuv\notes.txt",
        r"C:\Users\ramuv\todo.txt",
        r"C:\Users\ramuv\project\readme.md",
        r"C:\Users\ramuv\data\config.json",
        r"C:\Users\ramuv\Documents\agenda.txt",
        r"C:\Users\ramuv\workspace\build.log",
        r"C:\Users\ramuv\Desktop\meeting_notes.md",
        r"C:\Users\ramuv\Downloads\summary.txt",
        r"C:\Users\ramuv\AppData\Local\YANA\.env",
        r"C:\Users\ramuv\project\package.json",
        r"C:\Users\ramuv\docs\setup.md",
        r"C:\Users\ramuv\code\main.py",
        r"C:\Users\ramuv\settings.yaml",
        r"C:\Users\ramuv\report.csv",
        r"C:\Users\ramuv\data\test_cases.jsonl",
        r"C:\Users\ramuv\audit.log"
    ]
    variants = [
        "show system info",
        "show system information",
        "take a screenshot",
        "capture screen",
    ]
    cases = []
    for v in variants:
        cases.append({
            "text": v,
            "category": "exact_command",
            "expected_domain": "system_app",
            "expected_reasoning_tier": "routine",
            "mode": "control",
            "is_exact_command": True,
        })
    for app in apps:
        cases.append({
            "text": f"open app {app}",
            "category": "exact_command",
            "expected_domain": "system_app",
            "expected_reasoning_tier": "routine",
            "mode": "control",
            "is_exact_command": True,
        })
    for f in files:
        cases.append({
            "text": f'read file "{f}"',
            "category": "exact_command",
            "expected_domain": "system_app",
            "expected_reasoning_tier": "routine",
            "mode": "control",
            "is_exact_command": True,
        })
        cases.append({
            "text": f"read file '{f}'",
            "category": "exact_command",
            "expected_domain": "system_app",
            "expected_reasoning_tier": "routine",
            "mode": "control",
            "is_exact_command": True,
        })
        if len(cases) >= 54:
            break
    return cases[:54]


def get_compound_command_cases() -> List[Dict[str, Any]]:
    actions = [
        "open notepad and write a summary of the quarterly results",
        "take a screenshot and open paint to annotate it",
        "find all .log files in C:\\Logs and move them to C:\\Archive",
        "read file C:\\data\\v1.json and compare it with C:\\data\\v2.json",
        "open the browser, search for NVIDIA documentation, and download the PDF",
        "check my disk space and delete temporary log files in C:\\Temp",
        "inspect git status, pull latest changes, and run the test suite",
        "take a screenshot, save it to Desktop, and show system information",
        "open calc.exe and compute 4950 divided by 15",
        "create a new directory named ProjectAlpha and initialize a git repo",
        "open Edge, navigate to GitHub, and check notifications",
        "list running processes, find high CPU consumers, and log their PIDs",
        "extract the archive C:\\Downloads\\bundle.zip to C:\\Projects and build it",
        "read the error log in C:\\logs\\app.log and email the traceback to admin",
        "open notepad, write down the current date and time, and save to C:\\timestamp.txt",
        "find all python files modified today and run ruff check on them",
        "search for files larger than 100MB on drive C and list top 10",
        "open calculator, add up numbers from C:\\totals.csv, and save result",
        "take a screenshot of the active window and paste it into Word",
        "backup database.sqlite to C:\\Backups and verify checksum",
        "open terminal, start python dev server, and open browser preview",
        "scan folder C:\\Downloads for duplicate images and move to Trash",
        "download https://example.com/data.csv, parse rows, and plot histogram",
        "stop background workers, clean build artifacts, and rebuild release binary",
        "read config.ini, update port to 8080, and restart the service",
        "find all markdown files in docs and convert them to HTML",
        "check battery percentage and adjust display brightness accordingly",
        "verify git branch, merge feature-cartesia into main, and push",
        "open cmd.exe, ping 8.8.8.8 five times, and save output to ping.txt",
        "search for TODO comments in apps/agent and compile a checklist",
        "open Paint, draw a red rectangle, and save as diagram.png",
        "check internet connection speed and log results to network.log",
        "find all .bak files older than 30 days and permanently delete them",
        "copy C:\\notes.txt to D:\\Backup and append today's date",
        "open task manager, monitor memory for 10 seconds, and summarize",
        "format C:\\Users\\ramuv\\data.json with 2 spaces and overwrite",
        "open browser, go to weather.com, and report current humidity",
        "search recent system event logs for critical errors and display them",
        "read package.json, find outdated dependencies, and report them",
        "take 3 screenshots at 5-second intervals and save to Desktop",
        "open notepad.exe and paste the current clipboard contents",
        "list files in Downloads sorted by size and ask for deletion approval",
        "inspect port 8765, terminate any conflicting process, and start agent",
        "compile Rust binary with cargo build --release and measure compile time",
        "read user feedback from feedback.txt and generate a sentiment report",
        "create directory C:\\test_env, setup python venv, and install pytest",
        "check free disk space on all mounted drives and alert if below 10%",
        "open Edge, search for Python asyncio tutorial, and bookmark page",
        "find all empty folders in C:\\Users\\ramuv and clean them up",
        "record 5 seconds of audio, transcribe to text, and search Google",
        "fetch latest weather for London, Paris, and Tokyo and make a comparison table",
        "read database schema from schema.sql and generate markdown documentation",
        "inspect docker containers, restart stopped ones, and check logs",
        "run npm test and notify me via voice when finished"
    ]
    cases = []
    for act in actions:
        cases.append({
            "text": act,
            "category": "compound_command",
            "expected_domain": "mixed_or_unclear",
            "expected_reasoning_tier": "complex",
            "mode": "control",
            "is_exact_command": False,
        })
    return cases[:54]


def get_negated_command_cases() -> List[Dict[str, Any]]:
    negations = [
        "Don't delete anything, just explain what config.ini contains.",
        "Do not open notepad.exe, just tell me where it is located on Windows.",
        "Never execute commands without asking; first show me the syntax for listing ports.",
        "Do not modify the file, only show me lines 10 to 50 of app.py.",
        "Stop before running any script, just explain the potential risks of npm audit fix --force.",
        "Please don't run calc.exe, I only wanted to know its command line arguments.",
        "Do not launch the browser; summarize the topic of quantum computing here in chat.",
        "Don't restart the computer, just tell me how long it has been running.",
        "Do not delete the old database backup under any circumstances.",
        "Don't execute the sql query, just check if the syntax is valid.",
        "Do not send the email yet, I want to review the draft first.",
        "Don't close Edge, I have unsaved form inputs in one of the tabs.",
        "Do not install any new global packages, use the local virtual environment.",
        "Don't overwrite output.csv; create a new file named output_v2.csv instead.",
        "Do not terminate process 4120, that is the background audio service.",
        "Don't change my system volume, just tell me what the current level is.",
        "Do not wipe the cache folder, only delete files ending in .tmp.",
        "Don't push changes to git remote, keep them on my local branch.",
        "Do not plan any destructive operations without explicit confirmation.",
        "Don't download the large video file, only fetch the transcript text.",
        "Do not run the python script directly; inspect it for syntax errors first.",
        "Don't open Paint, just tell me which graphic formats it supports.",
        "Do not format drive D, that drive contains my family photo archives.",
        "Don't create new files in C:\\Windows; use C:\\Users\\ramuv\\AppData instead.",
        "Do not reboot into safe mode, let us troubleshoot in normal mode first.",
        "Don't mute the microphone, I am about to speak.",
        "Do not send diagnostic telemetry to any third-party cloud endpoint.",
        "Don't run benchmarks right now because my laptop battery is at 15%.",
        "Do not touch files in the node_modules folder.",
        "Don't execute sudo or admin commands without showing the command first.",
        "Do not convert the WAV file to MP3, keep it as uncompressed PCM.",
        "Don't minimize the active window while I am reading the document.",
        "Do not replace the model weights file with a fresh download.",
        "Don't auto-save changes until I click save explicitly.",
        "Do not enable auto-update; I want to stay on version 0.1.0.",
        "Don't write passwords or API keys to the terminal output.",
        "Do not run pip install with --break-system-packages.",
        "Don't archive files that were modified less than 24 hours ago.",
        "Do not kill the task if it is making active network progress.",
        "Don't clear the browser cookies, only clear cached images.",
        "Do not print entire files to console; limit output to 20 lines.",
        "Don't switch from Ollama to cloud provider without user permission.",
        "Do not start audio playback if headphones are not connected.",
        "Don't run disk defragmentation on an SSD drive.",
        "Do not remove the temporary directory until all tests finish.",
        "Don't execute shell commands that contain pipe operators.",
        "Do not modify registry keys under HKEY_LOCAL_MACHINE.",
        "Don't create desktop shortcuts automatically.",
        "Do not plan tools if the user is in Chat mode.",
        "Don't ignore permission denied errors; fail immediately.",
        "Do not download models in the background when on metered Wi-Fi.",
        "Don't close background tasks upon window minimization.",
        "Do not run stress tests when CPU temperature exceeds 80C.",
        "Don't log raw user messages to audit_logs database."
    ]
    cases = []
    for neg in negations:
        cases.append({
            "text": neg,
            "category": "negated_command",
            "expected_domain": "conversation",
            "expected_reasoning_tier": "complex",
            "mode": "chat",
            "is_exact_command": False,
        })
    return cases[:54]


def get_quoted_command_cases() -> List[Dict[str, Any]]:
    quoted = [
        'What does the command "show system info" do on Windows?',
        'Explain why someone would run "open app notepad.exe".',
        'Is the command "take a screenshot" safe to run in powershell?',
        'Where does "capture screen" save its output by default?',
        'How is "read file \\"C:\\\\notes.txt\\"" handled by the agent?',
        'What does "open app calc.exe" return if calculator is not installed?',
        'Explain the purpose of "netstat -ano | findstr 8765" in networking.',
        'Why would a developer run "git reset --hard HEAD~1"?',
        'What are the side effects of running "rmdir /s /q C:\\Temp"?',
        'Can you explain what "ipconfig /flushdns" does?',
        'Is "chmod 777 -R /" a good practice in Linux?',
        'What does "python -m venv .venv" do under the hood?',
        'Explain what "npm install --legacy-peer-deps" actually changes.',
        'What is the meaning of "taskkill /F /IM explorer.exe"?',
        'Why do people use "ping 127.0.0.1 -t" to check network stacks?',
        'What does "sfc /scannow" look for in Windows system files?',
        'Explain the syntax of "robocopy C:\\Source D:\\Dest /MIR /MT:8".',
        'How does "docker system prune -a --volumes" affect stored containers?',
        'What does "uv pip install --no-deps" do differently from pip?',
        'Explain the command "git bisect start" and how it helps find bugs.',
        'What does "Get-Process | Sort-Object CPU -Descending" output?',
        'Why is "curl -sSf | sh" considered risky by security researchers?',
        'Explain what "cat /dev/urandom | tr -dc A-Za-z0-9" is used for.',
        'What does the instruction "cargo build --release --offline" do?',
        'Explain the difference between "git merge" and "git rebase".',
        'What does "pytest -k \\"not slow\\"" do during test runs?',
        'Explain why "SET PATH=%PATH%;C:\\tools" affects the current session only.',
        'What does "DISM /Online /Cleanup-Image /RestoreHealth" repair?',
        'Why would an administrator run "net user guest /active:no"?',
        'Explain what "chkdsk C: /f /r" does on physical hard drives.',
        'What is the purpose of "python -m cProfile -s time script.py"?',
        'Explain what "tail -f /var/log/syslog" accomplishes.',
        'What does "systemctl restart systemd-resolved" do in Ubuntu?',
        'Explain the meaning of "wmic process get Caption,ProcessId".',
        'What does the command "npm run build:prod" do in YANA?',
        'Why would you run "pip check" after upgrading dependencies?',
        'Explain how "mklink /D link target" works in NTFS filesystems.',
        'What does "ssh -L 8080:localhost:8080 user@remote" do?',
        'Explain what "powershell -ExecutionPolicy Bypass -File setup.ps1" does.',
        'What happens when you run "dir /a:h C:\\"?',
        'Why do tutorials suggest "export PYTHONUNBUFFERED=1"?',
        'Explain what "kill -9 $PID" does compared to "kill -15 $PID".',
        'What does "git checkout --force main" do to uncommitted files?',
        'Explain what "attrib +h +s secret.txt" does on Windows.',
        'What is the function of "rundll32.exe user32.dll,LockWorkStation"?',
        'Why would you run "tracert 8.8.8.8" to diagnose connection lag?',
        'Explain what "npm cache clean --force" does to ~/.npm.',
        'What does "findstr /s /i \\"password\\" *.ini" search for?',
        'Explain the purpose of "git stash pop" in daily workflows.',
        'What does "docker compose up -d --build" do in multi-container setups?',
        'Why do tutorials use "grep -rnw \'/path/to/somewhere/\' -e \'pattern\'"?',
        'Explain what "openssl rand -hex 32" generates.',
        'What does "Get-Service | Where-Object Status -eq Running" show?',
        'Explain the effect of "shutdown /r /t 0" on Windows.'
    ]
    cases = []
    for q in quoted:
        cases.append({
            "text": q,
            "category": "quoted_command",
            "expected_domain": "conversation",
            "expected_reasoning_tier": "routine",
            "mode": "chat",
            "is_exact_command": False,
        })
    return cases[:54]


def get_ambiguous_cases() -> List[Dict[str, Any]]:
    ambiguous = [
        "do it again",
        "open that thing from earlier",
        "what about the other one?",
        "can you fix it?",
        "more details please",
        "???",
        "and then?",
        "run the last command again but better",
        "show me that file we looked at yesterday",
        "it didn't work",
        "why?",
        "check that",
        "run it",
        "do the needful",
        "try again",
        "undo that",
        "make it faster",
        "help me with this",
        "continue",
        "next",
        "what does it mean?",
        "is it done yet?",
        "look at the screen",
        "where is it?",
        "open something interesting",
        "do what you usually do",
        "start the task",
        "process that data",
        "clean up the mess",
        "fix the bug in there",
        "show me the output",
        "run another one",
        "can we proceed?",
        "yes please",
        "no that's not right",
        "maybe later",
        "what happened?",
        "inspect the error",
        "re-run with options",
        "send it over",
        "save it somewhere",
        "delete that thing",
        "copy that over here",
        "modify the second parameter",
        "check if it is ready",
        "update everything",
        "is there any problem?",
        "tell me more",
        "summarize it",
        "compare both",
        "open that app",
        "read the text",
        "take a look",
        "what next?"
    ]
    cases = []
    for amb in ambiguous:
        cases.append({
            "text": amb,
            "category": "ambiguous",
            "expected_domain": "mixed_or_unclear",
            "expected_reasoning_tier": "unclear",
            "mode": "chat",
            "is_exact_command": False,
        })
    return cases[:54]


def get_failure_related_cases() -> List[Dict[str, Any]]:
    failures = []
    for i in range(1, 55):
        failures.append({
            "text": f"open app non_existent_program_{i}.exe",
            "category": "failure_related",
            "expected_domain": "system_app",
            "expected_reasoning_tier": "routine",
            "mode": "control",
            "is_exact_command": False,
        })
    return failures[:54]


def get_code_terminal_cases() -> List[Dict[str, Any]]:
    code = [
        "Write a Python script to parse JSON files and calculate totals.",
        "Refactor this binary search function to prevent integer overflow.",
        "Run pytest on tests/test_router.py and show any failing assertions.",
        "Write a PowerShell script that monitors memory usage every 5 seconds.",
        "Debug this Python snippet: IndexError in nested loops.",
        "Write a Dockerfile for a Python FastAPI app using uv and python 3.11.",
        "Create a unit test using pytest for the authentication module.",
        "Implement an LRU cache in Python with get and put in O(1) time.",
        "Write a TypeScript interface matching this OpenAPI 3.0 schema.",
        "Create a bash script to backup PostgreSQL database to AWS S3 daily.",
        "Write a Rust function that computes SHA-256 hash of a file stream.",
        "Implement a debounce decorator in Python with configurable wait milliseconds.",
        "Refactor this database query to use parameterized prepared statements.",
        "Write a Python asyncio script to fetch 10 URLs concurrently with semaphore of 3.",
        "Debug why this React component re-renders infinitely on state change.",
        "Write a C++ class implementing a thread-safe circular ring buffer.",
        "Write a script to convert CSV data into SQLite database tables.",
        "Implement a trie data structure in Python for fast prefix search.",
        "Write a pytest fixture that sets up an isolated temporary SQLite database.",
        "Refactor this monolithic function into smaller single-responsibility helpers.",
        "Write a Python script to monitor a folder and process incoming images.",
        "Implement rate limiting using a token bucket algorithm in Python.",
        "Write a Tauri v2 command in Rust that returns available disk space on drive C.",
        "Create a GitHub Actions workflow that runs linting, formatting, and tests on PR.",
        "Debug a memory leak in Node.js caused by unclosed event listeners.",
        "Write an algorithm to detect cycles in a directed graph using Kahn's algorithm.",
        "Implement merge sort in Python and compare performance with Timsort.",
        "Write a script to validate email addresses using RFC 5322 regex.",
        "Create a Python CLI using argparse with subcommands for init, run, and status.",
        "Write a SQL query with window functions to find the 2nd highest salary per dept.",
        "Implement a custom exception hierarchy for an API client library in Python.",
        "Write a function that calculates Levenshtein edit distance between two strings.",
        "Create a script that parses Nginx access logs and reports 4xx/5xx status frequencies.",
        "Write a Rust struct with custom serde Serialize and Deserialize implementations.",
        "Implement a priority queue using Python's heapq module with custom comparator.",
        "Write a websocket client in Python that auto-reconnects with exponential backoff.",
        "Refactor this code to follow SOLID principles and add docstrings.",
        "Write a benchmark script using timeit to compare dict lookup vs set lookup.",
        "Create a mock for an external payment gateway in unit tests using unittest.mock.",
        "Write a Python function to compress and decompress strings using zlib.",
        "Implement a sliding window maximum algorithm with O(n) time complexity.",
        "Write a script to generate synthetic test data with faker in Python.",
        "Create a shell script that checks SSL certificate expiry date for domain list.",
        "Write a Python context manager that measures and logs execution time of a code block.",
        "Implement an event emitter pattern in JavaScript without external libraries.",
        "Write a script to extract all hyperlinks from an HTML string using BeautifulSoup.",
        "Refactor this recursive function to use an iterative approach with explicit stack.",
        "Write a Python script that calculates moving average of a stream of sensor values.",
        "Create a unit test testing timeout handling of an HTTP client using respx.",
        "Write a Rust function that parses command line arguments using clap.",
        "Implement Dijkstra's shortest path algorithm with adjacency list representation.",
        "Write a script to clean up trailing whitespace across all files in repository.",
        "Create an async generator in Python that reads large files chunk by chunk.",
        "Write a Python script that checks for dead code using vulture."
    ]
    cases = []
    for c in code:
        cases.append({
            "text": c,
            "category": "code_terminal",
            "expected_domain": "code_terminal",
            "expected_reasoning_tier": "complex",
            "mode": "control",
            "is_exact_command": False,
        })
    return cases[:54]


def get_browser_cases() -> List[Dict[str, Any]]:
    browser = [
        "Open Microsoft Edge and navigate to https://news.ycombinator.com",
        "Search Google for FastAPI background tasks and summarize the top 3 results",
        "Go to github.com/astral-sh/uv and check what the latest release version is",
        "Open browser, find documentation for Playwright, and extract code examples",
        "Navigate to https://python.org and take a screenshot of the download page",
        "Open browser and check today's stock price for NVIDIA on Yahoo Finance",
        "Search for flights from Seattle to Tokyo in May and find lowest prices",
        "Navigate to Wikipedia page for Alan Turing and extract biographical summary",
        "Open Edge, search for local Italian restaurants with 4.5+ star rating",
        "Go to pypi.org/project/laya and check the declared package dependencies",
        "Open browser, navigate to weather.com, and report tomorrow's rain forecast",
        "Search Google Scholar for recent papers on non-autoregressive decision models",
        "Go to github.com/tauri-apps/tauri/releases and list highlights of v2.0",
        "Open browser and find the official documentation for Windows NSIS packaging",
        "Navigate to https://crates.io and find the most downloaded async runtime crate",
        "Open Edge and inspect the HTTP status code of https://httpbin.org/status/404",
        "Search for documentation on torch.set_num_threads and explain its effect on CPU",
        "Go to https://news.google.com and summarize the top 5 technology news headlines",
        "Open browser, navigate to Reddit r/Python, and list the top 3 trending posts today",
        "Search for instructions on fixing Windows error 0x80070005 permission denied",
        "Open Edge, go to huggingface.co/convaiinnovations/laya, and read model card",
        "Navigate to MDN Web Docs and check browser compatibility for Web Audio API",
        "Search for tutorial on configuring Cartesia TTS API in Python applications",
        "Open browser, go to amazon.com, and search for ergonomic mechanical keyboards",
        "Navigate to speedtest.net and initiate a network speed test in the browser",
        "Search for NVIDIA Parakeet speech recognition model documentation on NGC",
        "Open Edge, go to stackoverflow.com, and search for asyncio cancellation errors",
        "Navigate to https://distrowatch.com and check top 5 Linux distributions this month",
        "Search for recipes for homemade sourdough bread with 70% hydration",
        "Open browser, go to cplusplus.com, and find the reference for std::unique_ptr",
        "Navigate to https://archive.org and search for public domain classical music recordings",
        "Open Edge, search for differences between Edge TTS and commercial TTS services",
        "Go to github.com/trending/python and report the top 3 trending Python repos",
        "Open browser, navigate to duckduckgo.com, and search for privacy friendly search engines",
        "Search for how to configure Windows Task Scheduler via PowerShell script",
        "Open Edge, navigate to https://dev.to, and find articles about AI agents",
        "Go to https://playwright.dev/python/docs/intro and summarize installation steps",
        "Open browser and check the current exchange rate from USD to EUR",
        "Search for best practices for securing local REST APIs in desktop applications",
        "Navigate to https://w3.org and find the official specification for WebSockets",
        "Open Edge and check if the website https://downforeveryoneorjustme.com is reachable",
        "Search for comparison between PyInstaller and Nuitka for packaging PyTorch apps",
        "Go to https://unsplash.com and find high resolution images of mountain landscapes",
        "Open browser, navigate to https://lobste.rs, and summarize top discussions",
        "Search for guidelines on handling audio input permissions in Tauri webviews",
        "Open Edge, navigate to npmjs.com/package/@tauri-apps/api, and check version",
        "Search for troubleshooting steps when Playwright Chromium fails to launch on Windows",
        "Go to https://docs.python.org/3/library/multiprocessing.html and check spawn vs fork",
        "Open browser and check upcoming SpaceX rocket launches on spaceflightnow.com",
        "Navigate to https://fastapi.tiangolo.com/tutorial/bigger-applications/ and review routers",
        "Open Edge and find the documentation for Intel Core i7-1360P Iris Xe graphics",
        "Search for how to measure resident set size (RSS) accurately with psutil in Python",
        "Navigate to https://sqlite.org/wal.html and explain write-ahead logging benefits",
        "Open browser and check latest security advisories on cve.mitre.org"
    ]
    cases = []
    for b in browser:
        cases.append({
            "text": b,
            "category": "browser",
            "expected_domain": "browser",
            "expected_reasoning_tier": "complex",
            "mode": "control",
            "is_exact_command": False,
        })
    return cases[:54]


def get_files_cases() -> List[Dict[str, Any]]:
    files = [
        "Search for all PDF files in C:\\Users\\ramuv\\Documents modified in last 7 days.",
        "Count total lines of code across all .py files in C:\\Projects\\Yana.",
        "Find and delete all empty folders under C:\\Users\\ramuv\\Downloads.",
        "Create a zip archive of C:\\Users\\ramuv\\Desktop\\Notes and save to D:\\Backup.",
        "Check disk usage breakdown for each folder inside C:\\Users\\ramuv.",
        "Find duplicate files by SHA-256 hash in C:\\Users\\ramuv\\Pictures.",
        "Rename all .jpeg files in C:\\Images to have the .jpg extension.",
        "Find all files containing the word 'TODO' in C:\\Users\\ramuv\\Yana\\apps.",
        "Sort all files in C:\\Downloads into subfolders by file extension.",
        "Calculate the total size of all node_modules directories on drive C.",
        "Archive log files older than 14 days from C:\\Logs into C:\\Logs\\Archive.zip.",
        "Find the largest 10 files in C:\\Users\\ramuv and display their paths and sizes.",
        "Convert all CRLF line endings to LF in C:\\Projects\\web\\src.",
        "Extract all files from backup.tar.gz into C:\\RestoredFiles.",
        "Search for files modified between 9 AM and 5 PM yesterday on drive C.",
        "Check if C:\\Users\\ramuv\\data\\records.csv contains any empty rows.",
        "Move all screenshots from C:\\Users\\ramuv\\Desktop to C:\\Pictures\\Screenshots.",
        "Generate a tree view of directories in C:\\Users\\ramuv\\Yana up to depth 3.",
        "Find all hidden files in C:\\Users\\ramuv and output their names.",
        "Compute MD5 and SHA-256 checksums for installer.exe and save to hashes.txt.",
        "Scan folder C:\\Music and organize audio files into Artist\\Album structure.",
        "Find all temporary files matching *.tmp or *.bak on drive C and report count.",
        "Search C:\\Projects for any .env files that may accidentally be tracked by git.",
        "Split a large 500MB log file into 50MB chunks.",
        "Compare two directories C:\\DirA and C:\\DirB and list missing or modified files.",
        "Find all read-only files in C:\\Users\\ramuv\\Documents and remove read-only flag.",
        "Search for text 'API_KEY' across all files in C:\\Workspace to audit leaks.",
        "Merge 5 separate CSV files in C:\\Data into a single combined.csv file.",
        "Create a daily backup folder named with today's date in C:\\Backups.",
        "Find all .git directories on drive C and list their repository names.",
        "Identify zero-byte files in C:\\Users\\ramuv\\Downloads and ask before deletion.",
        "Count how many image files (.png, .jpg, .webp) exist in C:\\Media.",
        "Compress C:\\Database\\sqlite.db using 7zip with maximum compression.",
        "Find all files whose names contain spaces and replace spaces with underscores.",
        "Search for Python virtual environment folders across all project directories.",
        "Extract text from all .docx files in C:\\Contracts and save as plain text.",
        "List all files in C:\\Windows\\System32 created in the last 24 hours.",
        "Check permissions on C:\\Users\\ramuv\\AppData\\Local\\YANA\\.env file.",
        "Find all JSON files with syntax errors in C:\\Config.",
        "Create a symbolic link from C:\\Project\\shared to C:\\SharedLibs.",
        "Search for all video files larger than 1GB in C:\\Videos.",
        "Find all XML files matching schema v2 in C:\\XmlData.",
        "Export directory structure of C:\\Users\\ramuv\\Documents to an Excel file.",
        "Audit C:\\Users\\ramuv\\Downloads and identify files that have not been opened in 6 months.",
        "Clean up temporary files created by PyInstaller in %LOCALAPPDATA%\\Temp.",
        "Verify that all markdown files in C:\\Docs have valid frontmatter blocks.",
        "Search for files created by user 'ramuv' in the last hour.",
        "List all installed fonts in C:\\Windows\\Fonts.",
        "Find all audio files with sample rate other than 16000 Hz in C:\\Audio.",
        "Check disk space freed if C:\\Users\\ramuv\\AppData\\Local\\Temp is emptied.",
        "Find all .log files with errors and compile an incident report.",
        "Search for uncommitted modified files across all repositories in C:\\Projects.",
        "Identify corrupted image files in C:\\Photos that cannot be opened.",
        "Backup registry hive HKEY_CURRENT_USER\\Software\\YANA to yana_reg.bak."
    ]
    cases = []
    for f in files:
        cases.append({
            "text": f,
            "category": "files",
            "expected_domain": "files",
            "expected_reasoning_tier": "complex",
            "mode": "control",
            "is_exact_command": False,
        })
    return cases[:54]


def build_full_dataset() -> List[Dict[str, Any]]:
    builders = [
        get_ordinary_chat_cases,
        get_exact_command_cases,
        get_compound_command_cases,
        get_negated_command_cases,
        get_quoted_command_cases,
        get_ambiguous_cases,
        get_failure_related_cases,
        get_code_terminal_cases,
        get_browser_cases,
        get_files_cases,
    ]

    all_cases: List[Dict[str, Any]] = []
    case_idx = 1

    for builder in builders:
        cat_cases = builder()
        # Ensure 54 per category -> 540 total
        assert len(cat_cases) == 54, f"Category {builder.__name__} has {len(cat_cases)} cases, expected 54"
        
        # Split: 32 train (~60%), 11 calibration (~20%), 11 test (~20%) -> 54 per cat
        random.shuffle(cat_cases)
        for i, c in enumerate(cat_cases):
            if i < 32:
                split = "train"
            elif i < 43:
                split = "calibration"
            else:
                split = "test"
            c["id"] = f"case_{case_idx:04d}"
            c["split"] = split
            all_cases.append(c)
            case_idx += 1

    all_cases.sort(key=lambda x: x["id"])
    return all_cases


def save_dataset(cases: List[Dict[str, Any]]):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with open(CASES_FILE, "w", encoding="utf-8") as f:
        for c in cases:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    hasher = hashlib.sha256()
    with open(CASES_FILE, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    cases_hash = hasher.hexdigest()

    split_counts = {"train": 0, "calibration": 0, "test": 0}
    cat_counts: Dict[str, int] = {}
    tier_counts: Dict[str, int] = {}

    for c in cases:
        split_counts[c["split"]] += 1
        cat_counts[c["category"]] = cat_counts.get(c["category"], 0) + 1
        tier_counts[c["expected_reasoning_tier"]] = tier_counts.get(c["expected_reasoning_tier"], 0) + 1

    manifest = {
        "version": "1.0.0",
        "total_cases": len(cases),
        "cases_sha256": cases_hash,
        "split_counts": split_counts,
        "category_counts": cat_counts,
        "reasoning_tier_counts": tier_counts,
        "splits": {
            "train": {"description": "Development and exploratory analysis split", "count": split_counts["train"]},
            "calibration": {"description": "Temperature and abstention threshold tuning", "count": split_counts["calibration"]},
            "test": {"description": "Frozen held-out evaluation split", "count": split_counts["test"]},
        },
        "provenance": "Synthesized from reviewed YANA system tasks, command parser rules, and desktop assistant interaction scenarios with distinct semantic categories.",
    }

    with open(MANIFEST_FILE, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"[+] Successfully wrote {len(cases)} cases to {CASES_FILE}")
    print(f"    Split breakdown: {split_counts}")
    print(f"    Category counts: {cat_counts}")
    print(f"    Manifest written to {MANIFEST_FILE} (SHA-256: {cases_hash})")


if __name__ == "__main__":
    cases = build_full_dataset()
    save_dataset(cases)
