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
from ulauncher.api.shared.action.ExtensionCustomAction import ExtensionCustomAction
from ulauncher.api.shared.action.HideWindowAction import HideWindowAction

CONFIG_FILE_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), "config.json") # Use os.path.realpath to get correct path in Ulauncher context
DEFAULT_SEARCH_PATHS = [os.path.expanduser("~")]
FIND_COMMAND_TIMEOUT = 5
KEYWORD_ADD_PATH = "unity_add_path"
KEYWORD_LIST_PATHS = "unity_list_paths"
KEYWORD_REMOVE_PATH = "unity_remove_path"

def load_search_paths(notify_errors=True):
    """Loads search paths from config.json, defaults to DEFAULT_SEARCH_PATHS if config is missing or invalid."""
    global BROADER_SEARCH_PATHS # Ensure we update the global
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
        if notify_errors:
            print(f"Warning: An unexpected error occurred while loading config.json: {e}. Using default search paths.")
    current_paths = DEFAULT_SEARCH_PATHS
    BROADER_SEARCH_PATHS = current_paths # Update global immediately
    return current_paths

def save_search_paths(paths):
    """Saves the given list of paths to config.json."""
    global BROADER_SEARCH_PATHS, CACHED_PROJECTS_LIST
    try:
        # Ensure paths are absolute and expanded
        expanded_paths = [os.path.expanduser(p) for p in paths if p.strip()]
        # Remove duplicates while preserving order
        unique_paths = []
        for p in expanded_paths:
            if p not in unique_paths:
                unique_paths.append(p)

        with open(CONFIG_FILE_PATH, "w", encoding='utf-8') as f:
            json.dump({"search_paths": unique_paths}, f, indent=2)
        BROADER_SEARCH_PATHS = unique_paths # Update global
        CACHED_PROJECTS_LIST = None # Clear project cache
        return True
    except Exception as e: # pylint: disable=broad-except
        print(f"Error: Could not save search paths to config.json: {e}")
        return False

BROADER_SEARCH_PATHS = load_search_paths() # Initial load


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
        global CACHED_PROJECTS_LIST, BROADER_SEARCH_PATHS
        
        items = []
        query_full = event.get_query() # Get the full query including keyword
        keyword = event.get_keyword() # Get the keyword used by user
        
        # Determine actual keywords from manifest.json
        prefs = extension.preferences
        main_keyword = prefs.get('unity_kw', 'unity') # Default to 'unity' if not found
        add_path_keyword = prefs.get('add_path_kw', KEYWORD_ADD_PATH)
        list_paths_keyword = prefs.get('list_paths_kw', KEYWORD_LIST_PATHS)
        remove_path_keyword = prefs.get('remove_path_kw', KEYWORD_REMOVE_PATH)

        argument = event.get_argument() or ""

        if keyword == add_path_keyword:
            if not argument:
                items.append(ExtensionResultItem(icon='images/unity.png',
                                                 name="Add Search Path",
                                                 description="Usage: {} <path_to_add>".format(add_path_keyword)))
                return RenderResultListAction(items)

            new_path = os.path.expanduser(argument.strip())
            if not os.path.isdir(new_path):
                items.append(ExtensionResultItem(icon='images/unity.png',
                                                 name="Invalid Path",
                                                 description=f"The path '{new_path}' is not a valid directory."))
                return RenderResultListAction(items)

            current_paths = load_search_paths(notify_errors=False) # Load current paths without printing warnings to ulauncher log for this action
            if new_path not in current_paths:
                current_paths.append(new_path)
                if save_search_paths(current_paths):
                    items.append(ExtensionResultItem(icon='images/unity.png',
                                                     name="Path Added Successfully",
                                                     description=f"Added '{new_path}'. Project list will be refreshed.",
                                                     on_enter=HideWindowAction()))
                else:
                    items.append(ExtensionResultItem(icon='images/unity.png',
                                                     name="Error Adding Path",
                                                     description="Could not save the new path. Check logs."))
            else:
                items.append(ExtensionResultItem(icon='images/unity.png',
                                                 name="Path Already Exists",
                                                 description=f"The path '{new_path}' is already in search paths.",
                                                 on_enter=HideWindowAction()))
            return RenderResultListAction(items)

        elif keyword == list_paths_keyword:
            current_paths = load_search_paths(notify_errors=False)
            if not current_paths:
                items.append(ExtensionResultItem(icon='images/unity.png',
                                                 name="No Search Paths Configured",
                                                 description=f"Use '{add_path_keyword} <path>' to add one."))
            else:
                items.append(ExtensionResultItem(icon='images/unity.png',
                                                 name="Current Search Paths:",
                                                 description="Select a path to see removal option (not yet implemented)."))
                for i, path_str in enumerate(current_paths):
                    items.append(ExtensionResultItem(icon='images/unity.png',
                                                     name=path_str,
                                                     description=f"Path {i+1}. Type '{remove_path_keyword} {path_str}' to remove (or click).",
                                                     on_enter=ExtensionCustomAction({"action": "copy_path", "path": path_str}))) # Placeholder for remove
            return RenderResultListAction(items)
        
        elif keyword == remove_path_keyword:
            path_to_remove = os.path.expanduser(argument.strip())
            if not argument:
                items.append(ExtensionResultItem(icon='images/unity.png',
                                                 name="Remove Search Path",
                                                 description="Usage: {} <path_to_remove>. List paths with '{}'.".format(remove_path_keyword, list_paths_keyword)))
                return RenderResultListAction(items)

            current_paths = load_search_paths(notify_errors=False)
            if path_to_remove in current_paths:
                current_paths.remove(path_to_remove)
                if save_search_paths(current_paths):
                    items.append(ExtensionResultItem(icon='images/unity.png',
                                                     name="Path Removed Successfully",
                                                     description=f"Removed '{path_to_remove}'. Project list will be refreshed.",
                                                     on_enter=HideWindowAction()))
                else:
                    items.append(ExtensionResultItem(icon='images/unity.png',
                                                     name="Error Removing Path",
                                                     description="Could not save changes. Check logs."))
            else:
                items.append(ExtensionResultItem(icon='images/unity.png',
                                                 name="Path Not Found",
                                                 description=f"The path '{path_to_remove}' is not in the search list."))
            return RenderResultListAction(items)


        # Default behavior: Search for projects (main_keyword)
        elif keyword == main_keyword:
            if CACHED_PROJECTS_LIST is None: # or BROADER_SEARCH_PATHS has changed
                # This print is for debugging if paths are not updating.
                # print(f"Unity Launcher: Refreshing projects. Current search paths: {BROADER_SEARCH_PATHS}")
                CACHED_PROJECTS_LIST = find_projects()
            
            projects = CACHED_PROJECTS_LIST
            
            if projects:
                filtered_projects = [
                    p for p in projects 
                    if argument.lower() in p[0].lower() or argument.lower() in p[1].lower() # Use argument here
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
                                description=f"Path: {path}. Unity Editor for this version ({version}) could not be found or accessed.",
                                on_enter=None # Or an action to inform the user
                            )
                        )
            
            if not items: # This covers no projects found, or no matching projects after filter
                if not projects:
                     description_text = "No Unity projects found. Use '{} <path>' to add search paths.".format(add_path_keyword)
                elif not argument: # Projects exist, but no query typed yet
                     description_text = "Unity projects found. Start typing to search or manage paths with other keywords."
                else: # Projects exist, query typed, but no match
                     description_text = f"No Unity project matching '{argument}' found. Try other keywords or manage paths."

                items.append(
                    ExtensionResultItem(
                        icon='images/unity.png',
                        name="Unity Project Launcher",
                        description=description_text
                    )
                )
            return RenderResultListAction(items)
        
        # Fallback for unrecognized keywords for this extension
        items.append(ExtensionResultItem(icon='images/unity.png', name="Unknown Unity Command", description=f"Keyword '{keyword}' not recognized by Unity Launcher."))
        return RenderResultListAction(items)

if __name__ == '__main__':
    # Ensure BROADER_SEARCH_PATHS is loaded when run directly, though Ulauncher handles its own lifecycle.
    if not BROADER_SEARCH_PATHS: BROADER_SEARCH_PATHS = load_search_paths()
    UnityExtension().run()
