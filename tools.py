import os
import re
import subprocess
from typing import Dict, Any, List, Optional

class ToolError(Exception):
    """Exception raised for errors during tool execution."""
    pass

class SafeToolExecutor:
    """
    Implements a set of sandboxed tools that can inspect, write, and verify
    code within a specified target repository. Path validation is enforced.
    """
    def __init__(self, target_repo_path: str):
        self.target_repo_path = os.path.abspath(target_repo_path)
        if not os.path.isdir(self.target_repo_path):
            raise ValueError(f"Target repository path is not a directory: {self.target_repo_path}")
        self.backup_dir = None
        self.changes_manifest = []

    def set_backup_dir(self, backup_dir: str):
        self.backup_dir = os.path.abspath(backup_dir)

    def _resolve_and_validate_path(self, relative_or_absolute_path: str) -> str:
        """
        Resolves path and checks if it falls within the target repository directory.
        Raises ToolError if it lies outside the repo.
        """
        # If relative, join with target repo path
        if not os.path.isabs(relative_or_absolute_path):
            abs_path = os.path.abspath(os.path.join(self.target_repo_path, relative_or_absolute_path))
        else:
            abs_path = os.path.abspath(relative_or_absolute_path)

        # Get real path to resolve symlinks
        real_path = os.path.realpath(abs_path)
        real_repo_path = os.path.realpath(self.target_repo_path)

        # Check if real_path is within real_repo_path
        # We add a trailing separator to prevent matching prefixes (e.g. /myrepo and /myrepo2)
        repo_prefix = real_repo_path if real_repo_path.endswith(os.sep) else real_repo_path + os.sep
        
        if real_path != real_repo_path and not real_path.startswith(repo_prefix):
            raise ToolError(
                f"Security violation: path '{relative_or_absolute_path}' (resolved to '{real_path}') "
                f"lies outside authorized target repository '{real_repo_path}'."
            )
        return real_path

    def list_files(self, relative_path: str = ".") -> List[str]:
        """
        Recursively lists all files in the given path within the target repository.
        Excludes typical search-noise directories like .git, node_modules, __pycache__, venv.
        """
        try:
            target_dir = self._resolve_and_validate_path(relative_path)
            if not os.path.isdir(target_dir):
                raise ToolError(f"'{relative_path}' is not a directory.")

            files_list = []
            exclude_dirs = {".git", "node_modules", "__pycache__", "venv", ".venv", ".gitmodules"}
            for root, dirs, files in os.walk(target_dir):
                # Prune excluded directories in place
                dirs[:] = [d for d in dirs if d not in exclude_dirs]
                for file in files:
                    full_path = os.path.join(root, file)
                    # Get path relative to the target repository
                    rel_to_repo = os.path.relpath(full_path, self.target_repo_path)
                    files_list.append(rel_to_repo.replace(os.sep, "/"))
            return sorted(files_list)
        except Exception as e:
            raise ToolError(f"Failed to list files: {str(e)}")

    def read_file(self, relative_path: str, start_line: Optional[int] = None, end_line: Optional[int] = None) -> str:
        """
        Reads the contents of a file. Supports optional 1-indexed start and end line bounds.
        """
        try:
            file_path = self._resolve_and_validate_path(relative_path)
            if not os.path.isfile(file_path):
                raise ToolError(f"File not found: '{relative_path}'")

            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            if start_line is not None or end_line is not None:
                total_lines = len(lines)
                start = max(1, start_line) if start_line is not None else 1
                end = min(total_lines, end_line) if end_line is not None else total_lines

                if start > total_lines:
                    return f"Empty: file only has {total_lines} lines."

                selected_lines = lines[start - 1 : end]
                # Include line numbers in output to help model references
                output_lines = [f"{start + idx}: {line}" for idx, line in enumerate(selected_lines)]
                return "".join(output_lines)
            else:
                return "".join(lines)
        except Exception as e:
            raise ToolError(f"Failed to read file: {str(e)}")

    def write_file(self, relative_path: str, content: str) -> str:
        """
        Writes complete content to a file inside the target repository.
        Creates parent directories automatically if they do not exist.
        """
        try:
            file_path = self._resolve_and_validate_path(relative_path)
            # Backup before writing if file exists
            if os.path.exists(file_path):
                self._backup_file(relative_path, file_path)
            else:
                # Record as new file if not already recorded
                if not any(c["file"] == relative_path for c in self.changes_manifest):
                    self.changes_manifest.append({
                        "file": relative_path,
                        "type": "new"
                    })

            # Create parent directories if they don't exist
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"Successfully wrote {len(content)} characters to '{relative_path}'"
        except Exception as e:
            raise ToolError(f"Failed to write file: {str(e)}")

    def edit_file(self, relative_path: str, target: str, replacement: str) -> str:
        """
        Performs search-and-replace modification of a file block inside the target repository.
        Expects target to match exactly one block of code in the file.
        """
        try:
            file_path = self._resolve_and_validate_path(relative_path)
            if not os.path.isfile(file_path):
                raise ToolError(f"File not found: '{relative_path}'")

            # Backup before editing
            self._backup_file(relative_path, file_path)

            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()

            occurrences = content.count(target)
            if occurrences == 0:
                raise ToolError(
                    f"Target block not found in '{relative_path}'. "
                    f"Make sure you match whitespaces, indentation, and newlines exactly."
                )
            if occurrences > 1:
                raise ToolError(
                    f"Target block matches {occurrences} times in '{relative_path}'. "
                    f"Please specify a larger unique block to avoid ambiguity."
                )

            new_content = content.replace(target, replacement, 1)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(new_content)

            return f"Successfully edited '{relative_path}'"
        except Exception as e:
            raise ToolError(f"Failed to edit file: {str(e)}")

    def _backup_file(self, relative_path: str, file_path: str):
        if not self.backup_dir:
            return
        if any(c["file"] == relative_path for c in self.changes_manifest):
            return
        try:
            backup_file_path = os.path.join(self.backup_dir, relative_path)
            os.makedirs(os.path.dirname(backup_file_path), exist_ok=True)
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                orig_content = f.read()
            with open(backup_file_path, "w", encoding="utf-8") as f:
                f.write(orig_content)
            self.changes_manifest.append({
                "file": relative_path,
                "type": "modify",
                "backup_path": os.path.relpath(backup_file_path, os.path.dirname(self.backup_dir)).replace(os.sep, "/")
            })
        except Exception as e:
            raise ToolError(f"Failed to backup file '{relative_path}' before modification: {str(e)}")

    def search_code(self, query: str, relative_path: str = ".") -> List[Dict[str, Any]]:
        """
        Performs a case-insensitive search for query text in all files in the target repository.
        Returns a list of match entries containing filename, line number, and line content.
        """
        try:
            search_dir = self._resolve_and_validate_path(relative_path)
            matches = []
            exclude_dirs = {".git", "node_modules", "__pycache__", "venv", ".venv"}
            
            for root, dirs, files in os.walk(search_dir):
                dirs[:] = [d for d in dirs if d not in exclude_dirs]
                for file in files:
                    full_path = os.path.join(root, file)
                    rel_to_repo = os.path.relpath(full_path, self.target_repo_path).replace(os.sep, "/")
                    try:
                        with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                            for idx, line in enumerate(f, 1):
                                if query.lower() in line.lower():
                                    matches.append({
                                        "file": rel_to_repo,
                                        "line_number": idx,
                                        "line_content": line.strip()
                                    })
                                    if len(matches) >= 50:
                                        # Cap results to avoid blowing out token context
                                        return matches
                    except Exception:
                        # Skip files that can't be read (e.g. binaries)
                        continue
            return matches
        except Exception as e:
            raise ToolError(f"Failed to search code: {str(e)}")

    def run_command(self, command: str) -> str:
        """
        Runs a shell command inside the target repository directory.
        Forces PAGER=cat and returns standard output/error combined.
        """
        try:
            # Enforce execution in target repository
            env = os.environ.copy()
            env["PAGER"] = "cat"
            
            # Using shell=True for windows command execution compatibility
            # and running it inside the resolved repository path.
            result = subprocess.run(
                command,
                shell=True,
                cwd=self.target_repo_path,
                env=env,
                capture_output=True,
                text=True,
                timeout=60  # Prevent infinite hangs
            )
            
            output = []
            if result.stdout:
                output.append(result.stdout)
            if result.stderr:
                output.append(result.stderr)
            
            combined = "".join(output)
            return f"Command exited with code {result.returncode}.\nOutput:\n{combined}"
        except subprocess.TimeoutExpired:
            return "Command execution timed out after 60 seconds."
        except Exception as e:
            raise ToolError(f"Failed to execute command: {str(e)}")
