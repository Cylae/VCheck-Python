# 🦢 Project: The Swan

*"We're gonna have to enter the numbers again. And again. And again."*

---

## 🧭 Orientation: Welcome to Station 3

Welcome, new recruit. You've been assigned to **Station 3: The Swan**. Your primary directive is to maintain and operate this system. The system's purpose is to scan for and neutralize temporal anomalies (in this case, corrupted video files) before another "incident" occurs.

Remember to push the button.

**Current System Protocol: `4.8.15.16.23.42`**

---

## 🤓 Technical Summary for Experts

For those who just want to get going:

*   **Language:** Python 3.6+
*   **Core Dependency:** FFmpeg (must be in system PATH)
*   **Python Libraries:** `rich`, `send2trash`, `psutil`. The script will offer to auto-install these via `pip` on first run.
*   **Execution:** `python VChecker.py`
*   **Functionality:** Interactively scans a directory for corrupt video files using FFmpeg, then allows the user to select and move them to the recycle bin.

---

## 🚀 Getting Started on Windows 11 (for Novices)

This guide will walk you through setting up the system on a fresh Windows 11 machine. Follow these steps precisely to prevent system failure.

### Phase 0: Get the Project Files 📂

Before you can begin, you need the project files on your computer.

1.  On the main page of this repository, find the green button labeled **`< > Code`**.
2.  Click this button. A dropdown menu will appear.
3.  Select **"Download ZIP"**.
4.  Save the ZIP file, then **unzip it** to a location you'll remember (like your Desktop or Downloads folder). This creates your project folder.

*(For advanced users: you can also `git clone` the repository URL found in the same "< > Code" menu.)*

### Phase 1: Install Python 🐍

The system requires Python to function.

1.  Go to the official Python website: [https://www.python.org/downloads/](https://www.python.org/downloads/)
2.  Download the latest stable Python installer for Windows.
3.  Run the installer. **Crucially**, on the first screen, check the box that says **"Add Python to PATH"**.
4.  Proceed with the default installation settings.
5.  To verify, open a new Command Prompt or PowerShell window and type `python --version`. If it shows a version number, you are ready for the next phase.

### Phase 2: Install FFmpeg 🎬

FFmpeg is the core analysis engine. It must be accessible to the system.

1.  Go to the official FFmpeg download page: [https://ffmpeg.org/download.html](https://ffmpeg.org/download.html)
2.  Click the **Windows logo** to get the Windows builds. A common source for up-to-date builds is `gyan.dev`.
3.  Download a "full" build `.zip` or `.7z` file.
4.  Create a permanent folder on your computer, for example `C:\ffmpeg`.
5.  Extract the contents of the downloaded archive into `C:\ffmpeg`. You should now have a folder structure like `C:\ffmpeg\bin`, `C:\ffmpeg\doc`, etc.
6.  **Add FFmpeg to the PATH:**
    *   Press the `Windows` key and type `env`.
    *   Select **"Edit the system environment variables"**.
    *   In the System Properties window, click the **"Environment Variables..."** button.
    *   In the "System variables" section (the bottom half), find and select the `Path` variable, then click **"Edit..."**.
    *   Click **"New"** and add the path to FFmpeg's `bin` folder. Using our example, you would add: `C:\ffmpeg\bin`.
    *   Click OK on all windows to save the changes.
7.  To verify, open a new Command Prompt and type `ffmpeg -version`. If it shows details about the FFmpeg build, the installation was successful.

### Phase 3: Running The Swan Protocol ▶️

Now you are ready to initialize the system.

1.  Open a Command Prompt or PowerShell window.
2.  Navigate to the project folder you created in Phase 0 using the `cd` command (e.g., `cd Desktop\TheSwan-main`).
3.  Run the script using the command: `python VChecker.py`
4.  **First-Time Initialization:** The script will detect missing components (`rich`, `send2trash`, `psutil`) and ask for permission to install them. Type `y` and press Enter. The script will install them and then close. This is normal.
5.  **Re-engage the System:** Run the script again: `python VChecker.py`.
6.  The interactive menu will now appear. You are now in control. Follow the on-screen prompts.

---

*Namaste... and good luck.*

<!-- "See you in another life, brotha." -->
