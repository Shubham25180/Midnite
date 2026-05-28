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
            "name": "take_screenshot",
            "description": (
                "Capture the screen and analyze it using the vision model. "
                "Use when the user says 'what's on my screen', 'read this error', "
                "'describe what you see', 'what does this form say', or any request "
                "that requires seeing the current state of the desktop or a window."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": (
                            "What to ask the vision model about the screen. "
                            "Examples: 'What error message is showing?', "
                            "'What form fields are visible?', "
                            "'Read all the text on screen.'"
                        ),
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_browse",
            "description": (
                "Fetch a URL using a real browser with JavaScript execution. "
                "Use this for lyrics sites, news articles, SPAs, dashboards — "
                "any page that returns blank content with web_fetch. "
                "Slower than web_fetch but works on JS-rendered pages. "
                "Optional: selector (CSS) to extract specific content; "
                "wait_for (text string) to wait for before extracting."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Full URL to browse"},
                    "selector": {
                        "type": "string",
                        "description": "CSS selector to extract (e.g. '.lyrics', '#content'). Leave empty for full page.",
                    },
                    "wait_for": {
                        "type": "string",
                        "description": "Wait for this text to appear before extracting (useful for SPAs)",
                    },
                },
                "required": ["url"],
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
            "name": "read_word",
            "description": (
                "Read a Word document (.docx) and return its text content. "
                "Preserves headings, paragraphs, bullet points, and tables. "
                "Use when the user provides or references a .docx file."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the .docx file"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_spreadsheet",
            "description": (
                "Write structured data to a CSV or XLSX spreadsheet file. "
                "rows is a list of objects where keys become column headers. "
                "Use .csv for simple data; use .xlsx for formatted Excel with bold headers. "
                "Use when the user wants to export data, generate a report, or save a table."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Output file path — must end in .csv or .xlsx",
                    },
                    "rows": {
                        "type": "array",
                        "description": (
                            'List of objects where each key is a column header. '
                            'Example: [{"Name": "Alice", "Score": 95}, {"Name": "Bob", "Score": 88}]'
                        ),
                        "items": {"type": "object"},
                    },
                    "sheet": {
                        "type": "string",
                        "description": "Worksheet name for .xlsx (default 'Sheet1')",
                    },
                },
                "required": ["path", "rows"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_word",
            "description": (
                "Create a Word document (.docx) from structured text content. "
                "Supports headings (# ## ###), bullet lists (- item), numbered lists (1. item), "
                "tables (| col | col | rows), and regular paragraphs. "
                "Use when the user wants a formatted report, letter, or document as a .docx file."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Output file path — must end in .docx",
                    },
                    "content": {
                        "type": "string",
                        "description": (
                            "Document content using simple markdown-like syntax:\n"
                            "  # Title        → Heading 1\n"
                            "  ## Section     → Heading 2\n"
                            "  - bullet       → Bullet point\n"
                            "  1. item        → Numbered list\n"
                            "  | col | col |  → Table row\n"
                            "  plain text     → Paragraph"
                        ),
                    },
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_pdf",
            "description": (
                "Read a PDF file and return its text content. "
                "For text-based PDFs, extracts text directly (fast). "
                "For scanned/image PDFs, uses vision OCR automatically. "
                "Supports page ranges: 'all', '1-5', '3'. "
                "Use dpi=300 for invoices, forms, or small-text documents."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the PDF file"},
                    "pages": {
                        "type": "string",
                        "description": "Pages to read: 'all' (default), '1-5', or '3'",
                    },
                    "dpi": {
                        "type": "integer",
                        "description": (
                            "OCR resolution for scanned pages. "
                            "200 = default (general docs), "
                            "300 = invoices/forms/small text, "
                            "150 = fast/low-quality. Range: 150-400."
                        ),
                    },
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_spreadsheet",
            "description": (
                "Read an Excel (.xlsx, .xls) or CSV file. "
                "Returns column names, row count, and a preview of the data. "
                "Use sheet parameter to select a specific worksheet."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the spreadsheet file"},
                    "sheet": {
                        "type": "string",
                        "description": "Sheet name to read (Excel only; defaults to active sheet)",
                    },
                    "max_rows": {
                        "type": "integer",
                        "description": "Max rows to return in preview (default 100)",
                    },
                },
                "required": ["path"],
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
    {
        "type": "function",
        "function": {
            "name": "browser_action",
            "description": (
                "Interact with a live persistent browser page — click buttons, fill forms, "
                "navigate, scrape JS-rendered content, and automate web workflows. "
                "ALWAYS call get_snapshot first after navigating to see all interactive elements. "
                "click tries CSS/text/role matching (Approach A) then falls back to "
                "vision model pixel coordinates (Approach B) automatically. "
                "Use web_browse for simple read-only fetching; use browser_action when you "
                "need to interact (click, type, select, hover) or when state must persist "
                "across multiple steps."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": [
                            "navigate", "get_snapshot", "click", "type",
                            "hover", "scroll", "wait", "get_text", "select", "screenshot",
                        ],
                        "description": (
                            "navigate — go to URL. "
                            "get_snapshot — dump accessibility tree (call this first). "
                            "click — click an element (A11y → vision fallback). "
                            "type — clear + type text into an input. "
                            "hover — hover over element (triggers dropdowns/tooltips). "
                            "scroll — scroll page or scroll element into view. "
                            "wait — wait for element/text to appear. "
                            "get_text — return inner text of element. "
                            "select — pick an option from a <select> dropdown. "
                            "screenshot — screenshot page and analyze with vision model."
                        ),
                    },
                    "url": {
                        "type": "string",
                        "description": "Full URL for navigate action (must start with http:// or https://)",
                    },
                    "selector": {
                        "type": "string",
                        "description": (
                            "CSS selector to target an element "
                            "(e.g. '#submit-btn', '.product-title', 'button[type=submit]'). "
                            "Preferred over text when the element has a stable CSS id/class."
                        ),
                    },
                    "text": {
                        "type": "string",
                        "description": (
                            "Visible text label of the element to interact with "
                            "(e.g. 'Add to Cart', 'Submit', 'Next'). "
                            "Tried exact then partial match."
                        ),
                    },
                    "role": {
                        "type": "string",
                        "description": (
                            "ARIA role to match (e.g. 'button', 'textbox', 'link', 'combobox'). "
                            "Combine with text for 'button named Submit'."
                        ),
                    },
                    "value": {
                        "type": "string",
                        "description": (
                            "For type: the text to type into the input. "
                            "For select: the option value or label to select. "
                            "For scroll: direction ('up'/'down'/'top'/'bottom') or pixel amount. "
                            "For screenshot: the vision prompt (what to describe)."
                        ),
                    },
                    "wait_for": {
                        "type": "string",
                        "description": "CSS selector to wait for before executing the action (useful after clicks that trigger navigation or dynamic content).",
                    },
                    "timeout_ms": {
                        "type": "integer",
                        "description": "Timeout in milliseconds (default 15000). Increase for slow pages.",
                    },
                },
                "required": ["action"],
            },
        },
    },
]

# Set of valid tool names — used by fallback parsers to distinguish tool calls from
# random function-like text in model responses.
TOOL_NAMES: frozenset[str] = frozenset(
    t["function"]["name"] for t in TOOL_DEFINITIONS
)
