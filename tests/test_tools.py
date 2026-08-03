import os
import tempfile
import pytest
from tools import SafeToolExecutor, ToolError

@pytest.fixture
def temp_repo():
    """Creates a temporary repository directory with some dummy files for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create some files and directories
        os.makedirs(os.path.join(tmpdir, "src"))
        os.makedirs(os.path.join(tmpdir, "node_modules"))  # Should be excluded
        
        with open(os.path.join(tmpdir, "README.md"), "w", encoding="utf-8") as f:
            f.write("Line 1: Hello World\nLine 2: AI Agent\nLine 3: Testing tools")
            
        with open(os.path.join(tmpdir, "src", "main.py"), "w", encoding="utf-8") as f:
            f.write("def run():\n    print('Running')\n\n# Duplicate line\n# Duplicate line")
            
        with open(os.path.join(tmpdir, "node_modules", "module.js"), "w", encoding="utf-8") as f:
            f.write("console.log('noise');")

        yield tmpdir

def test_path_safety_valid(temp_repo):
    executor = SafeToolExecutor(temp_repo)
    
    # Valid relative path
    resolved = executor._resolve_and_validate_path("README.md")
    assert resolved == os.path.realpath(os.path.join(temp_repo, "README.md"))
    
    # Valid absolute path inside repo
    abs_path = os.path.join(temp_repo, "src", "main.py")
    resolved = executor._resolve_and_validate_path(abs_path)
    assert resolved == os.path.realpath(abs_path)

def test_path_safety_invalid(temp_repo):
    executor = SafeToolExecutor(temp_repo)
    
    # Path traversal attempting to go outside repo
    with pytest.raises(ToolError) as excinfo:
        executor._resolve_and_validate_path("../some_other_folder")
    assert "lies outside authorized target repository" in str(excinfo.value)
    
    # Absolute path outside repo
    with pytest.raises(ToolError) as excinfo:
        executor._resolve_and_validate_path("C:\\Windows" if os.name == 'nt' else "/etc")
    assert "lies outside authorized target repository" in str(excinfo.value)

def test_list_files(temp_repo):
    executor = SafeToolExecutor(temp_repo)
    files = executor.list_files()
    
    # Excludes node_modules, includes others
    assert "README.md" in files
    assert "src/main.py" in files
    assert "node_modules/module.js" not in files

def test_read_file(temp_repo):
    executor = SafeToolExecutor(temp_repo)
    
    # Read entire file
    content = executor.read_file("README.md")
    assert "Hello World" in content
    
    # Read specific lines (1-indexed, returns line numbers)
    lines_content = executor.read_file("README.md", start_line=2, end_line=3)
    assert "2: Line 2: AI Agent" in lines_content
    assert "3: Line 3: Testing tools" in lines_content
    assert "1: Line 1" not in lines_content

def test_write_file(temp_repo):
    executor = SafeToolExecutor(temp_repo)
    
    # Write to new file
    msg = executor.write_file("src/utils.py", "def add(a, b): return a + b")
    assert "Successfully wrote" in msg
    assert os.path.exists(os.path.join(temp_repo, "src", "utils.py"))
    
    with open(os.path.join(temp_repo, "src", "utils.py"), "r") as f:
        assert f.read() == "def add(a, b): return a + b"

def test_edit_file(temp_repo):
    executor = SafeToolExecutor(temp_repo)
    
    # Edit single unique block
    msg = executor.edit_file("README.md", "Line 2: AI Agent", "Line 2: Smart AI Agent")
    assert "Successfully edited" in msg
    
    with open(os.path.join(temp_repo, "README.md"), "r") as f:
        content = f.read()
        assert "Line 2: Smart AI Agent" in content
        assert "Line 1: Hello World" in content
        
    # Attempt to edit block that does not exist
    with pytest.raises(ToolError) as excinfo:
        executor.edit_file("README.md", "Non existent line", "replacement")
    assert "Target block not found" in str(excinfo.value)
    
    # Attempt to edit non-unique block
    with pytest.raises(ToolError) as excinfo:
        executor.edit_file("src/main.py", "# Duplicate line", "# Replaced line")
    assert "matches 2 times" in str(excinfo.value)

def test_search_code(temp_repo):
    executor = SafeToolExecutor(temp_repo)
    
    # Search term exists
    matches = executor.search_code("Duplicate")
    assert len(matches) == 2
    assert matches[0]["file"] == "src/main.py"
    assert matches[0]["line_number"] == 4
    
    # Search term doesn't exist
    matches_empty = executor.search_code("notfound_term")
    assert len(matches_empty) == 0
