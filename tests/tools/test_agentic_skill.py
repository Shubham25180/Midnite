from Skynet.task.skills.agentic import AgenticSkill

sk = AgenticSkill()
cases = [
    ("create a weather skill", True),
    ("write me a Python function", True),
    ("show me what skills you have", True),
    ("run the tests", True),
    ("read the settings file", True),
    ("how are you doing", False),
    ("sing me a song", False),
    ("tell me a joke", False),
    ("what time is it", False),
    ("what skills do you have", True),
]
for text, expected in cases:
    result = sk.match(text)
    status = "OK  " if result == expected else "FAIL"
    tag = "agentic" if result else "chat   "
    print(f"{status} [{tag}] {text}")
