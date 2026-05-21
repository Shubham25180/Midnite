"""Tool schemas passed to LLMs that support function calling (Ollama, Claude API)."""
from __future__ import annotations

TOOL_DEFINITIONS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of any file in the project.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path relative to project root"}
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": (
                "Write content to a file. Creates it if it doesn't exist. "
                "Use this to create or edit skill files, configs, and code."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path relative to project root"},
                    "content": {"type": "string", "description": "Full content to write"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List all files and directories inside a directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "Directory path relative to project root (default '.')",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_bash",
            "description": (
                "Run any PowerShell command with full system access. "
                "Use for: git (status/log/diff/commit/push), python/pip, "
                "file ops (ls/cat/mkdir/cp/mv), grep/ripgrep/Select-String, "
                "tests, installs, network (curl/Invoke-WebRequest), "
                "process management, registry, environment vars — anything terminal. "
                "cmd.exe commands work too via: cmd /c 'your command'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "PowerShell command to execute"}
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_system_info",
            "description": (
                "Get live system status: running components with health states, "
                "loaded skills, memory entry count, current LLM model."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reload_skills",
            "description": (
                "Hot-reload skill definitions from disk. "
                "Call this after writing a new skill file so it takes effect immediately."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_all_files",
            "description": (
                "Read ALL files in a directory at once. "
                "Use this when the user asks you to read all files, understand a folder, "
                "or summarize an entire directory. Returns each file's content with a header. "
                "Respects size limits — large files are truncated."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "Directory path relative to project root (e.g. 'docs')",
                    },
                    "max_files": {
                        "type": "integer",
                        "description": "Max files to read (default 12)",
                    },
                },
                "required": ["directory"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_history",
            "description": (
                "Get the last N turns of conversation from this session's raw log. "
                "Use when the user asks to summarize or remember recent conversation, "
                "or when you need to refer to something said more than 6 turns ago."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "n_turns": {
                        "type": "integer",
                        "description": "Number of turns to retrieve (default 10, max 50)",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_memory",
            "description": (
                "Save something important to long-term memory. "
                "Use when the user says 'remember this', 'save this', or when you learn a key fact. "
                "Use importance='core' for things the user explicitly wants never forgotten; "
                "'important' for facts/preferences; 'summary' for session summaries."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "The text to remember"},
                    "importance": {
                        "type": "string",
                        "enum": ["core", "important", "summary"],
                        "description": "Memory tier: core (never forget), important (facts), summary (session recap)",
                    },
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_memory",
            "description": (
                "Search your long-term memory for past conversations, facts, and session summaries. "
                "Use this when the user asks what you remember, what happened before, or references "
                "something from a previous session."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "What to search for (e.g. 'what did we build last session')",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "glob_files",
            "description": (
                "Find files by glob pattern. "
                "Use '**/*.py' to find all Python files, '**/*.yaml' for YAML, "
                "'Skynet/core/*' for a specific folder. "
                "Returns matching paths sorted, up to 200 results."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Glob pattern relative to project root (e.g. '**/*.py', 'Skynet/**/*.yaml')",
                    }
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grep_files",
            "description": (
                "Search file contents for a regex pattern. "
                "Returns matching lines in 'file:line: content' format. "
                "Use file_glob to narrow the search (e.g. '**/*.py'). "
                "Skips __pycache__, .git, node_modules. Limit 200 matches."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Regex pattern to search for"},
                    "path": {
                        "type": "string",
                        "description": "Directory to search in (default '.')",
                    },
                    "file_glob": {
                        "type": "string",
                        "description": "Optional glob to filter files (e.g. '**/*.py')",
                    },
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": (
                "Make a precise string replacement in a file. "
                "Reads the file, replaces old_string with new_string exactly ONCE. "
                "Fails if old_string appears 0 or 2+ times (be more specific). "
                "Always read_file first so you know the exact current content."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path relative to project root"},
                    "old_string": {
                        "type": "string",
                        "description": "Exact text to replace (must be unique in the file)",
                    },
                    "new_string": {
                        "type": "string",
                        "description": "Text to replace it with",
                    },
                },
                "required": ["path", "old_string", "new_string"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "multi_edit_file",
            "description": (
                "Apply multiple precise string replacements to a single file in one call. "
                "Each edit is {old_string, new_string}. Applied sequentially. "
                "More efficient than calling edit_file repeatedly on the same file."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path relative to project root"},
                    "edits": {
                        "type": "array",
                        "description": "List of {old_string, new_string} pairs",
                        "items": {
                            "type": "object",
                            "properties": {
                                "old_string": {"type": "string"},
                                "new_string": {"type": "string"},
                            },
                            "required": ["old_string", "new_string"],
                        },
                    },
                },
                "required": ["path", "edits"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_fetch",
            "description": (
                "Fetch a URL and return its text content. "
                "HTML is stripped to plain text. Returns up to 8000 chars. "
                "Optionally provide a prompt describing what to extract."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Full URL to fetch (http/https only)"},
                    "prompt": {
                        "type": "string",
                        "description": "Optional: what to look for in the page",
                    },
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "load_skill",
            "description": (
                "Load the full instructions for a named skill. "
                "Call this when the user's request matches a skill from the skill index. "
                "After calling, follow the returned instructions exactly."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Skill name from the index (e.g. 'sing')",
                    }
                },
                "required": ["name"],
            },
        },
    },
]

# Set of valid tool names — used by fallback parsers to distinguish tool calls from
# random function-like text in model responses.
TOOL_NAMES: frozenset[str] = frozenset(
    t["function"]["name"] for t in TOOL_DEFINITIONS
)
