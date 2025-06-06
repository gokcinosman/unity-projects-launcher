import os
import subprocess
import time
import json
from ulauncher.api.client.Extension import Extension
from ulauncher.api.client.EventListener import EventListener
from ulauncher.api.shared.event import KeywordQueryEvent
from ulauncher.api.shared.item.ExtensionResultItem import ExtensionResultItem
from ulauncher.api.shared.action.RenderResultListAction import RenderResultListAction
from ulauncher.api.shared.action.RunScriptAction import RunScriptAction

CONFIG_FILE_PATH = os.path.join(os.path.dirname(__file__), "config.json")
DEFAULT_SEARCH_PATHS = [os.path.expanduser("~")]
FIND_COMMAND_TIMEOUT = 5

def load_search_paths():
    """Loads search paths from config.json, defaults to DEFAULT_SEARCH_PATHS if config is missing or invalid."""
    try:
        if os.path.exists(CONFIG_FILE_PATH):
            with open(CONFIG_FILE_PATH, "r", encoding='utf-8') as f:
                config_data = json.load(f)
                paths = config_data.get("search_paths")
                if isinstance(paths, list) and all(isinstance(p, str) for p in paths):
                    return [os.path.expanduser(p) for p in paths if p.strip()]
                else:
                    # Log error or notify user about invalid config format
                    print("Warning: Invalid format for 'search_paths' in config.json. Using default paths.")
        else:
            # Log error or notify user about missing config file
            print("Warning: config.json not found. Using default search paths.")
    except json.JSONDecodeError:
        # Log error or notify user about invalid JSON
        print("Warning: Error decoding config.json. Using default search paths.")
    except Exception as e: # pylint: disable=broad-except
        print(f"Warning: An unexpected error occurred while loading config.json: {e}. Using default search paths.")
    return DEFAULT_SEARCH_PATHS

BROADER_SEARCH_PATHS = load_search_paths()


def get_project_details_from_project_version_file(project_version_file_path):
    """
    Takes the path to ProjectVersion.txt and extracts the project name,
    root directory, and Unity version. Returns (name, project_root_path, version) or None.
    """
    try:
        project_settings_dir = os.path.dirname(project_version_file_path)
        if os.path.basename(project_settings_dir) != "ProjectSettings":
            return None
        
        project_root_path = os.path.dirname(project_settings_dir)
        project_name = os.path.basename(project_root_path)
        
        version = None
        with open(project_version_file_path, "r", encoding='utf-8') as f:
            for line in f:
                if line.startswith("m_EditorVersion:"):
                    version = line.strip().split(": ")[1]
                    break
        if version:
            return project_name, project_root_path, version
    except Exception: # pylint: disable=broad-except
        pass
    return None

def find_projects_with_find_command():
    """
    Uses the 'find' command to search for Unity projects within BROADER_SEARCH_PATHS.
    """
    projects = []
    valid_search_paths = [p for p in BROADER_SEARCH_PATHS if os.path.isdir(p)]
    if not valid_search_paths:
        return []

    command_parts = ["find"]
    command_parts.extend(valid_search_paths)
    command_parts.extend(["-path", "*/ProjectSettings/ProjectVersion.txt", "-type", "f", "-print0"])

    try:
        process = subprocess.Popen(command_parts, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate(timeout=FIND_COMMAND_TIMEOUT)

        if stderr:
            pass

        found_files_bytes = stdout.strip(b'\0').split(b'\0')
        
        for f_bytes in found_files_bytes:
            if not f_bytes:
                continue
            try:
                file_path = f_bytes.decode('utf-8')
                details = get_project_details_from_project_version_file(file_path)
                if details:
                    projects.append(details)
            except UnicodeDecodeError:
                continue
            except Exception: # pylint: disable=broad-except
                continue
    except subprocess.TimeoutExpired:
        pass
    except FileNotFoundError:
        pass
    except Exception: # pylint: disable=broad-except
        pass
        
    return projects


def find_projects(): 
    all_projects_dict = {}
    
    start_time_find = time.time()
    projects_from_find = find_projects_with_find_command()
    end_time_find = time.time()
    
    for project_details in projects_from_find:
        all_projects_dict[project_details[1]] = project_details

    return list(all_projects_dict.values())

CACHED_EDITORS = {}
EDITORS_SCANNED = False
CACHED_PROJECTS_LIST = None

def find_unity_editor(required_version):
    """
    Searches for the Unity editor of the specified version system-wide and returns its path.
    Caches found editors for performance.
    """
    global CACHED_EDITORS, EDITORS_SCANNED

    if required_version in CACHED_EDITORS:
        return CACHED_EDITORS[required_version]

    if EDITORS_SCANNED:
        return None

    editor_search_paths = BROADER_SEARCH_PATHS

    command_parts = ["find"]
    command_parts.extend(editor_search_paths)
    command_parts.extend(["-name", "Unity", "-type", "f", "-executable", "-print0"])
    
    found_editor_path_for_version = None
    start_time = time.time()

    try:
        process = subprocess.Popen(command_parts, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate(timeout=FIND_COMMAND_TIMEOUT)

        if stderr:
            pass

        found_executables_bytes = stdout.strip(b'\0').split(b'\0')
        
        for f_bytes in found_executables_bytes:
            if not f_bytes:
                continue
            try:
                executable_path = f_bytes.decode('utf-8')
                path_parts = executable_path.split(os.sep)
                if len(path_parts) >= 3 and path_parts[-2] == "Editor" and path_parts[-1] == "Unity":
                    editor_version_from_path = path_parts[-3]
                    if editor_version_from_path and editor_version_from_path[0].isdigit():
                        CACHED_EDITORS[editor_version_from_path] = executable_path
                        if editor_version_from_path == required_version:
                            found_editor_path_for_version = executable_path
            except UnicodeDecodeError:
                continue
            except Exception: # pylint: disable=broad-except
                continue
        
    except subprocess.TimeoutExpired:
        pass
    except FileNotFoundError:
        pass
    except Exception as e: # pylint: disable=broad-except
        print(f"ERROR: Error executing find command for Unity editors: {e}")

    end_time = time.time()
    EDITORS_SCANNED = True

    if required_version in CACHED_EDITORS:
        return CACHED_EDITORS[required_version]
        
    return found_editor_path_for_version

class UnityExtension(Extension):
    def __init__(self):
        super(UnityExtension, self).__init__()
        self.subscribe(KeywordQueryEvent, KeywordQueryEventListener())

class KeywordQueryEventListener(EventListener):
    def on_event(self, event, extension):
        global CACHED_PROJECTS_LIST
        query = event.get_argument() or ""
        
        overall_start_time = time.time()
        
        if CACHED_PROJECTS_LIST is None:
            CACHED_PROJECTS_LIST = find_projects()
        
        projects = CACHED_PROJECTS_LIST
        
        overall_end_time = time.time()

        items = []
        if projects:
            filtered_projects = [
                p for p in projects 
                if query.lower() in p[0].lower() or query.lower() in p[1].lower()
            ]

            for name, path, version in filtered_projects:
                editor_executable = find_unity_editor(version)
                if editor_executable:
                    items.append(
                        ExtensionResultItem(
                            icon='images/unity.png',
                            name=f"{name} ({version})",
                            description=f"Path: {path}",
                            on_enter=RunScriptAction(f'"{editor_executable}" -projectPath "{path}"', None)
                        )
                    )
                else:
                    items.append(
                        ExtensionResultItem(
                            icon='images/unity.png',
                            name=f"{name} ({version}) - Editor Not Found!",
                            description=f"Path: {path}. Unity Editor for this version ({version}) could not be found or accessed on your system.",
                            on_enter=None
                        )
                    )
        
        if not items:
            if not projects:
                 description_text = "No Unity projects found in the configured search paths."
            elif not query:
                 description_text = "Unity projects found. Start typing to search."
            else:
                 description_text = f"No Unity project matching '{query}' found. Check your project locations and search term."

            items.append(
                ExtensionResultItem(
                    icon='images/unity.png',
                    name="Unity Project Not Found",
                    description=description_text
                )
            )

        return RenderResultListAction(items)

if __name__ == '__main__':
    UnityExtension().run()
