# -*- coding: utf-8 -*-
"""
Video Corruption Cleaner - v10.0 (Final Interactive)

A robust, high-performance tool to find and delete corrupt video files using FFmpeg.

--------------------------------------------------------------------------------
USER GUIDE
--------------------------------------------------------------------------------

**1. DESCRIPTION**

This script recursively scans a specified directory for video files, uses FFmpeg
to analyze each file for corruption or read errors, and then interactively
prompts the user to delete the problematic files by moving them to the recycle bin.

**2. FEATURES**

* **Fully Interactive**: No command-line arguments needed. The script guides you
    through a visual menu to select folders and configure settings.
* **Automatic Dependency Management**: Checks for and offers to install required
    Python libraries on first run.
* **Focused Input**: The quit hotkey ([Q]) only works when the script's terminal
    window is active, preventing accidental closures.
* **No Admin Rights Needed**: The script no longer requires administrator
    privileges to run.
* **High-Performance Parallel Analysis**: Analyzes multiple files simultaneously
    to significantly speed up the process on multi-core CPUs.
* **User-Friendly Interface**: Uses a clean, responsive terminal UI with progress
    bars, tables, and color-coded information.
* **Safe Deletion**: Moves files to the system's recycle bin instead of
    permanently deleting them, allowing for recovery.
* **Network Drive Support**: Includes a local cache option to handle slow
    network drives (like Google Drive) by temporarily copying files locally
    before analysis, preventing timeouts.
* **Configurable Timeout**: Analysis runs indefinitely by default, but an optional
    timeout can be set for each file.
* **Session Management**: Save analysis reports and load them later to resume
    the deletion process without re-scanning.
* **Robust & Safe**: Includes checks for stray FFmpeg processes.

**3. REQUIREMENTS**

* **Python 3.6+**
* **FFmpeg**: Must be installed and accessible from the system's PATH. The script
    will guide you if FFmpeg is not found.

**4. FIRST-TIME USE**

The first time you run the script, it will check for the necessary Python
libraries (rich, send2trash, psutil) and ask for your permission to
install them if they are missing.

**5. USAGE**

Run the script from your terminal. It will guide you through an interactive menu.

--------------------------------------------------------------------------------
"""
import subprocess
import logging
import os
import shutil
import tempfile
import threading
import time
import sys
import importlib.util
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- Dependency Management ---
REQUIRED_PACKAGES = {
    "rich": "rich",
    "send2trash": "send2trash",
    "psutil": "psutil"
}

def check_and_install_dependencies():
    """Checks for required Python packages and offers to install them."""
    missing_packages = []
    for package_name, import_name in REQUIRED_PACKAGES.items():
        if importlib.util.find_spec(import_name) is None:
            missing_packages.append(package_name)

    if not missing_packages:
        return True

    print(f"Warning: The following required packages are not installed: {', '.join(missing_packages)}")
    response = input("Do you want to attempt to install them now? (y/n): ").lower()
    
    if response != 'y':
        print("Aborting. Please install the required packages manually.")
        return False

    print("Attempting to install missing packages with pip...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", *missing_packages], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("All required packages have been installed successfully.")
        print("Please restart the script for the changes to take effect.")
        return False
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("\nError: Failed to install packages with pip. Please try installing them manually:")
        print(f"pip install {' '.join(missing_packages)}")
        return False

if not check_and_install_dependencies():
    sys.exit(1)

# --- Dynamic Imports after check ---
try:
    import psutil
except ImportError:
    psutil = None
from send2trash import send2trash
from rich.console import Console, Group
from rich.table import Table
from rich.logging import RichHandler
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
from rich.prompt import Confirm, Prompt, IntPrompt
from rich.panel import Panel
from rich.text import Text
from rich.live import Live
import tkinter as tk
from tkinter import filedialog

# --- Configuration ---
VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm'}
LOG_FILE = "corruption_check_log.txt"
ANALYSIS_TIMEOUT = None

# --- Rich Console Initialization ---
console = Console(record=True)

# --- Logging Setup ---
logging.basicConfig(
    level="INFO", format="%(message)s", datefmt="[%X]",
    handlers=[
        logging.FileHandler(LOG_FILE, mode='w', encoding='utf-8'),
        RichHandler(console=console, show_time=False, show_path=False, rich_tracebacks=True, markup=True)
    ]
)

# --- Global Stop Mechanism ---
STOP_EVENT = threading.Event()
ACTIVE_PROCESSES = set()
PROCESS_LOCK = threading.Lock()

# --- Non-blocking, single-character input handling ---
# This replaces the 'keyboard' library to avoid global hooks and admin rights.
# It only captures input when the terminal window is in focus.
class _Getch:
    """Gets a single character from standard input without requiring Enter."""
    def __init__(self):
        try:
            self.impl = _GetchWindows()
        except ImportError:
            self.impl = _GetchUnix()

    def __call__(self): return self.impl()

class _GetchUnix:
    def __call__(self):
        import sys, tty, termios
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            char = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return char

class _GetchWindows:
    def __init__(self):
        import msvcrt
    def __call__(self):
        import msvcrt
        return msvcrt.getch().decode('utf-8', errors='ignore')

try:
    getch = _Getch()
    INPUT_LISTENER_ENABLED = True
except Exception:
    INPUT_LISTENER_ENABLED = False

def input_listener():
    """A thread that listens for 'q' or 'a' to stop the analysis."""
    if not INPUT_LISTENER_ENABLED: return
    while not STOP_EVENT.is_set():
        try:
            char = getch()
            if char in ('q', 'a', '\x03'): # q (QWERTY), a (AZERTY), Ctrl+C
                if not STOP_EVENT.is_set():
                    console.print("\n[bold red]Quit signal received. Shutting down analysis...[/bold red]")
                    STOP_EVENT.set()
                break
        except Exception:
            break

def start_input_listener():
    """Starts the input listener thread if possible."""
    if INPUT_LISTENER_ENABLED:
        listener_thread = threading.Thread(target=input_listener, daemon=True)
        listener_thread.start()
    else:
        logging.warning("Could not start keyboard listener. The quit hotkey will not be available.")

def clear_console():
    os.system('cls' if os.name == 'nt' else 'clear')

def check_and_kill_stray_ffmpeg():
    if not psutil: return True
    stray_processes = [proc for proc in psutil.process_iter(['pid', 'name']) if 'ffmpeg' in proc.info['name'].lower()]
    if not stray_processes: return True

    console.print(Panel(Text("Stray FFmpeg processes were found running.", justify="center"), title="[bold yellow]Warning[/bold yellow]", border_style="yellow"))
    table = Table(title="Running FFmpeg Processes")
    table.add_column("PID", style="cyan"); table.add_column("Name", style="magenta")
    for proc in stray_processes: table.add_row(str(proc.info['pid']), proc.info['name'])
    console.print(table)

    if Confirm.ask("[bold red]Do you want to terminate them to continue?[/bold red]", default=True):
        for proc in stray_processes:
            try: proc.kill()
            except Exception as e: logging.error(f"Failed to kill process {proc.info['pid']}: {e}")
        return True
    else:
        logging.warning("Aborting script. Please close stray FFmpeg processes manually.")
        return False

def cleanup_active_processes():
    with PROCESS_LOCK:
        active_procs = list(ACTIVE_PROCESSES)
        if not active_procs: return
        console.print(f"\n[yellow]Terminating {len(active_procs)} active FFmpeg processes...[/yellow]")
        for p in active_procs:
            try: p.terminate(); p.wait(timeout=5)
            except Exception: pass
        ACTIVE_PROCESSES.clear()

def is_ffmpeg_installed():
    console.print("[cyan]Checking for FFmpeg installation...[/cyan]")
    try:
        subprocess.run(['ffmpeg', '-version'], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        console.print("[green]✅ FFmpeg found successfully.[/green]")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        console.print(Panel(Text.from_markup("❌ [bold]FFmpeg is not installed or not in the system's PATH.[/bold]\n\nPlease download it from [bold cyan]https://ffmpeg.org/download.html[/bold cyan] and ensure its location is added to your system's PATH.", justify="center"), title="[bold red]FFmpeg Not Found[/bold red]", border_style="red"))
        return False

def check_video_corruption(original_path: Path, use_cache: bool, temp_dir: str) -> tuple[Path, bool, str]:
    path_to_analyze = original_path
    local_copy = None
    process = None

    if use_cache:
        try:
            local_copy = Path(temp_dir) / f"{os.urandom(8).hex()}-{original_path.name}"
            shutil.copy2(original_path, local_copy)
            path_to_analyze = local_copy
        except Exception as e:
            return original_path, True, f"Local copy error: {e}"

    try:
        command = ['ffmpeg', '-nostdin', '-v', 'error', '-i', str(path_to_analyze), '-f', 'null', '-']
        process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        with PROCESS_LOCK: ACTIVE_PROCESSES.add(process)

        start_time = time.time()
        while process.poll() is None:
            if STOP_EVENT.is_set():
                process.terminate(); process.wait(timeout=5)
                return original_path, False, "Cancelled"
            if ANALYSIS_TIMEOUT is not None and (time.time() - start_time > ANALYSIS_TIMEOUT):
                process.terminate(); process.wait(timeout=5)
                return original_path, True, f"Timeout ({ANALYSIS_TIMEOUT}s)"
            time.sleep(0.1)

        return (original_path, False, "Healthy") if process.returncode == 0 else (original_path, True, "Corruption detected")
    except Exception as e:
        return (original_path, False, "Cancelled") if STOP_EVENT.is_set() else (original_path, True, f"Unexpected error: {e}")
    finally:
        if process:
            with PROCESS_LOCK:
                if process in ACTIVE_PROCESSES: ACTIVE_PROCESSES.remove(process)
        if local_copy and local_copy.exists(): local_copy.unlink()

def run_analysis(video_files: list[Path], use_cache: bool, workers: int) -> list[tuple[Path, str]]:
    corrupted_files = []
    progress = Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), BarColumn(), TextColumn("[progress.percentage]{task.percentage:>3.0f}%"), TimeElapsedColumn(), console=console)
    footer_text = Text.from_markup("Press the [bold cyan]Q[/bold cyan] key to quit analysis", justify="center")
    live_group = Group(progress, Panel(footer_text, border_style="dim"))

    with Live(live_group, console=console, screen=False, redirect_stderr=False, vertical_overflow="visible") as live:
        with tempfile.TemporaryDirectory() as temp_dir:
            task = progress.add_task("[cyan]Analyzing files...", total=len(video_files))
            with ThreadPoolExecutor(max_workers=workers) as executor:
                future_to_file = {executor.submit(check_video_corruption, file, use_cache, temp_dir): file for file in video_files}
                for future in as_completed(future_to_file):
                    if STOP_EVENT.is_set(): break
                    try:
                        path, is_corrupted, reason = future.result()
                        if is_corrupted: corrupted_files.append((path, reason))
                    except Exception as e: logging.error(f"An analysis task failed: {e}")
                    progress.update(task, advance=1)
                if STOP_EVENT.is_set():
                    cleanup_active_processes()
                    executor.shutdown(wait=False, cancel_futures=True)
                    return []
    return sorted(corrupted_files, key=lambda x: x[0])

def select_files_for_deletion(corrupted_files: list[tuple[Path, str]]) -> list[Path]:
    console.rule("[bold red]Corrupted Files Report[/bold red]", style="red")
    table = Table(title="Corrupted or Problematic Video Files", style="red", title_style="bold red", expand=True)
    table.add_column("ID", style="cyan", justify="right", no_wrap=True); table.add_column("File Path", style="magenta"); table.add_column("Reason", style="yellow", no_wrap=True)
    for i, (file, reason) in enumerate(corrupted_files): table.add_row(str(i + 1), str(file), reason)
    console.print(table)

    console.rule("[bold yellow]Action Required[/bold yellow]", style="yellow")
    try:
        choice = Prompt.ask("\n[bold]Enter file IDs to delete (e.g., 1,3-5,8), 'all' for everything, or 'none' to cancel[/bold]", default="none").lower()
        if choice in ['none', 'n']: return []
        if choice in ['all', 'a', 'yes', 'y']: return [file for file, reason in corrupted_files]

        selected_files = set()
        for part in choice.replace(" ", "").split(','):
            if '-' in part:
                start, end = map(int, part.split('-'))
                for i in range(start, end + 1):
                    if 1 <= i <= len(corrupted_files): selected_files.add(corrupted_files[i - 1][0])
            else:
                i = int(part)
                if 1 <= i <= len(corrupted_files): selected_files.add(corrupted_files[i - 1][0])
        return list(selected_files)
    except (ValueError, IndexError):
        logging.error("Invalid input. Please enter numbers, ranges, 'all', or 'none'.")
        return []
    except (KeyboardInterrupt, EOFError):
        console.print("\n[yellow]Operation cancelled by user.[/yellow]")
        return []

def delete_files(files_to_delete: list[Path]):
    if not files_to_delete: logging.info("No files selected for deletion."); return
    delete_table = Table(title="Files to be Moved to Recycle Bin", style="yellow", title_style="bold yellow", expand=True)
    delete_table.add_column("Filename", style="magenta")
    for file in files_to_delete: delete_table.add_row(file.name)
    console.print(delete_table)

    if not Confirm.ask("[bold red]Do you confirm the deletion?[/bold red]", default=False):
        logging.info("Deletion cancelled."); return

    console.rule("[bold red]Deletion[/bold red]", style="red")
    deleted_count = 0
    with Progress(console=console) as progress:
        task = progress.add_task("[red]Deleting files...", total=len(files_to_delete))
        for file in files_to_delete:
            try: send2trash(str(file)); deleted_count += 1
            except Exception as e: logging.error(f"ERROR: Could not delete '{file.name}'. Reason: {e}")
            progress.update(task, advance=1)
    
    console.print(Panel(Text(f"Operation complete. {deleted_count}/{len(files_to_delete)} files were moved to the recycle bin.", justify="center"), title="[bold green]✅ Summary[/bold green]", border_style="green"))

def save_report(report_file: Path, corrupted_files: list[tuple[Path, str]]):
    try:
        with open(report_file, 'w', encoding='utf-8') as f:
            for path, reason in corrupted_files: f.write(f"{path}\t{reason}\n")
        logging.info(f"Report saved to [bold cyan]{report_file}[/bold cyan]")
    except IOError as e: logging.error(f"Could not save report: {e}")

def load_report(report_file: Path) -> list[tuple[Path, str]]:
    if not report_file.is_file(): logging.error(f"Report file '{report_file}' not found."); return []
    corrupted_files = []
    try:
        with open(report_file, 'r', encoding='utf-8') as f:
            for line in f:
                parts = line.strip().split('\t')
                if len(parts) == 2:
                    path, reason = Path(parts[0]), parts[1]
                    if path.exists(): corrupted_files.append((path, reason))
                    else: logging.warning(f"File listed in report not found, skipping: {path}")
        logging.info(f"Report loaded from [bold cyan]{report_file}[/bold cyan]")
        return corrupted_files
    except IOError as e:
        logging.error(f"Could not load report: {e}"); return []

def select_folder_dialog() -> str:
    """Opens a graphical dialog to select a folder."""
    root = tk.Tk(); root.withdraw()
    folder_path = filedialog.askdirectory(title="Select a Folder to Scan")
    root.destroy()
    return folder_path

def select_file_dialog() -> str:
    """Opens a graphical dialog to select a file."""
    root = tk.Tk(); root.withdraw()
    file_path = filedialog.askopenfilename(title="Select a Report File", filetypes=[("Text files", "*.txt")])
    root.destroy()
    return file_path

def run_interactive_setup():
    """Guides the user through an interactive setup process."""
    global ANALYSIS_TIMEOUT
    clear_console()
    console.print(Panel(Text("Video Corruption Cleaner", justify="center", style="bold blue"), subtitle="v10.0 (Final)"))
    
    config = {}
    
    menu_text = Text(justify="center")
    menu_text.append("1. 📁 Scan a new directory\n", style="cyan")
    menu_text.append("2. 📄 Load a previous report", style="cyan")
    console.print(Panel(menu_text, title="[bold]Main Menu[/bold]", border_style="blue"))
    
    mode = Prompt.ask("[bold]What would you like to do?[/bold]", choices=["1", "2"], default="1")
    
    if mode == "2":
        report_path = select_file_dialog()
        if not report_path: console.print("[red]No report file selected. Aborting.[/red]"); return None
        config['load_report'] = Path(report_path)
        return config

    # --- New Scan Setup ---
    target_dir = select_folder_dialog()
    if not target_dir: console.print("[red]No directory selected. Aborting.[/red]"); return None
    config['directory'] = Path(target_dir)

    console.rule("[bold blue]⚙️ Scan Settings[/bold blue]", style="blue")
    config['cache_local'] = Confirm.ask("Use local cache? (Recommended for network/cloud drives)", default=False)
    
    if Confirm.ask("Set a timeout for each file? (Default is infinite)", default=False):
        ANALYSIS_TIMEOUT = IntPrompt.ask("Enter timeout in seconds", default=300)
    
    config['workers'] = IntPrompt.ask("How many files to analyze at once?", default=os.cpu_count() or 1)
    
    if Confirm.ask("Save a report of corrupted files after analysis?", default=False):
        report_name = Prompt.ask("Enter report filename", default="corrupted_files_report.txt")
        config['save_report_path'] = Path(report_name)

    return config

def main_script(config: dict):
    """Main logic of the script, using the config dictionary."""
    if not config: return

    start_input_listener()
    corrupted_files = []

    try:
        if config.get('load_report'):
            corrupted_files = load_report(config['load_report'])
        else:
            if not is_ffmpeg_installed(): return
            
            console.rule("[bold blue]Phase 1: File Scanning[/bold blue]", style="blue")
            settings_text = Text(justify="left")
            settings_text.append("📁 Target Directory: ").append(str(config['directory'].resolve()), style="cyan")
            settings_text.append("\n⚙️ Analysis Workers: ").append(str(config['workers']), style="cyan")
            if config.get('cache_local'): settings_text.append("\n⚡ Local Cache Mode: ").append("Enabled", style="yellow")
            timeout_str = f"{ANALYSIS_TIMEOUT} seconds" if ANALYSIS_TIMEOUT is not None else "Infinite"
            settings_text.append("\n⏱️ Analysis Timeout: ").append(timeout_str, style="cyan")
            console.print(Panel(settings_text, title="[bold]Settings[/bold]", border_style="blue"))
            
            video_files = [p for p in config['directory'].rglob('*') if p.suffix.lower() in VIDEO_EXTENSIONS]
            if not video_files: logging.info("No video files found in the specified directory."); return

            logging.info(f"[bold]{len(video_files)}[/bold] video files found.")
            console.rule("[bold blue]Phase 2: Corruption Analysis[/bold blue]", style="blue")
            corrupted_files = run_analysis(video_files, config.get('cache_local', False), config['workers'])

        if STOP_EVENT.is_set(): console.print("\n[bold yellow]Analysis was interrupted by the user.[/bold yellow]"); return
        if not corrupted_files: console.print(Panel(Text("🎉 No corrupted videos were found. Your collection is clean!", justify="center"), title="[bold green]Analysis Complete[/bold green]", border_style="green")); return

        if config.get('save_report_path'): save_report(config['save_report_path'], corrupted_files)
        
        files_to_delete = select_files_for_deletion(corrupted_files)
        delete_files(files_to_delete)

    except (KeyboardInterrupt):
        console.print("\n[yellow]Keyboard interrupt detected. Cleaning up and shutting down.[/yellow]")
        cleanup_active_processes()
    finally:
        # No unhook needed for this input method
        pass

if __name__ == "__main__":
    try:
        if not check_and_kill_stray_ffmpeg():
            sys.exit(1)
            
        config = run_interactive_setup()
        if config:
            main_script(config)
    except Exception as e:
        console.print_exception()
        console.log(f"An unexpected error occurred: {e}")
