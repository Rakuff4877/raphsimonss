"""
MCP Google Drive tool constants and parameter formatters.

Claude Code uses these MCP tools to read from and write to Google Drive.
Python scripts call the Claude API; Drive I/O is handled by Claude Code via MCP.

MCP tool names (used in Claude Code tool calls):
  mcp__claude_ai_Google_Drive__search_files
  mcp__claude_ai_Google_Drive__read_file_content
  mcp__claude_ai_Google_Drive__create_file
  mcp__claude_ai_Google_Drive__get_file_metadata
  mcp__claude_ai_Google_Drive__download_file_content
"""

MIME_FOLDER = "application/vnd.google-apps.folder"
MIME_DOC = "application/vnd.google-apps.document"
MIME_SHEET = "application/vnd.google-apps.spreadsheet"
MIME_CSV = "text/csv"
MIME_JSON = "application/json"
MIME_TEXT = "text/plain"


def search_in_folder(name: str, parent_id: str, mime_type=None) -> dict:
    """Returns search_files params to find a file/folder by name within a parent."""
    parts = [f"name = '{name}'", f"'{parent_id}' in parents", "trashed = false"]
    if mime_type:
        parts.append(f"mimeType = '{mime_type}'")
    return {"query": " and ".join(parts)}


def create_folder_params(name: str, parent_id: str) -> dict:
    """Returns create_file params to create a Drive folder."""
    return {"name": name, "mimeType": MIME_FOLDER, "parents": [parent_id]}


def create_text_file_params(name: str, parent_id: str, content: str) -> dict:
    """Returns create_file params for a plain text file."""
    return {"name": name, "mimeType": MIME_TEXT, "parents": [parent_id], "content": content}


def create_csv_file_params(name: str, parent_id: str, content: str) -> dict:
    """Returns create_file params for a CSV file."""
    return {"name": name, "mimeType": MIME_CSV, "parents": [parent_id], "content": content}
