# Unity Project Launcher

This Ulauncher extension allows you to launch your Unity projects directly without opening Unity Hub. You can quickly search for your saved projects and open them with the desired Unity Editor version.

## Features

*   Quickly search and launch Unity projects via Ulauncher.
*   Searches for projects in user-configured directories.
*   Indicates if the correct Unity Editor version for the project is installed.
*   If the specified Editor version for a project is not found on your system, you will receive an "Editor Not Found!" warning.

## Preview

The extension lists your projects in Ulauncher search results as follows:

![Extension Usage Example](https://github.com/gokcinosman/unity-projects-launcher/blob/main/images/readme.png)

In the image:
*   **botanik (2022.3.59f1):** The associated Unity Editor version for this project is installed on your system, and the project is ready to be opened.
*   **MusicTycoon (2022.3.21f1) - Editor Not Found!:** The specified Unity Editor version for this project was not found on your system. You may need to install the relevant Editor version via Unity Hub to open the project.

## Configuration

For the extension to find your Unity projects, you need to tell it where to look.

1.  Open Ulauncher preferences (usually by typing `ulauncher-prefs` in Ulauncher or through your system's application menu).
2.  Go to the "Extensions" tab.
3.  Find "Unity Project Launcher" in the list and click on it or its settings icon.
4.  You will see a preference field named **"Unity Project Paths"**.
5.  In this field, enter the full paths to the directories where your Unity projects are stored.
    *   If you have multiple directories, enter **each path on a new line**.
    *   Example:
        ```
        /home/your_username/UnityProjects
        /mnt/data/Work/GameDevProjects
        ```
6.  The extension has a default path set to `/home/user/Documents/GitHub`. Please update this to reflect your actual project locations. If no paths are configured, or the configured paths do not contain Unity projects, the extension will not be able to find them.

## Usage

1.  Open Ulauncher (default shortcut `Ctrl + Space`).
2.  Enter the extension's keyword (`uni`).
3.  If you have configured project paths and have projects in them, they will be listed. Start typing to filter the list.
4.  Select one of your listed Unity projects and press `Enter/Space`.
5.  If the associated Editor version is installed, the project will open with the selected Editor.

## License

This project is licensed under the MIT License. See the `LICENSE` file for more details.
