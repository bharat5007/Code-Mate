from langchain_core.tools import tool


@tool
def write_code(file_path: str, new_content: str) -> str:
    """Overwrite a file with new_content. Use only when you have the complete new file content."""
    try:
        with open(file_path, "w") as f:
            f.write(new_content)
        return f"Successfully wrote to {file_path}"
    except Exception as e:
        return f"Error: {str(e)}"


@tool
def append_code(file_path: str, new_code: str) -> str:
    """Append new_code to the end of an existing file. Use when adding a new function or class without needing the full file content."""
    try:
        with open(file_path, "a") as f:
            f.write("\n\n" + new_code)
        return f"Successfully appended code to {file_path}"
    except Exception as e:
        return f"Error: {str(e)}"


@tool
def read_file(file_path: str) -> str:
    """Read content of a file. Use when you need to examine specific code."""
    try:
        with open(file_path, "r") as f:
            return f.read()
    except Exception as e:
        return f"Error: {str(e)}"


@tool
def run_terminal(command: str) -> str:
    """Run a terminal command. Only allowed: python, pytest, git."""
    ALLOWED = ("python", "pytest", "git")
    if not any(command.strip().startswith(cmd) for cmd in ALLOWED):
        return f"Command not allowed. Only {ALLOWED} are permitted."

    import subprocess

    result = subprocess.run(
        command, shell=True, capture_output=True, text=True, timeout=30
    )
    return result.stdout or result.stderr
