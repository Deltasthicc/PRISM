"""
Ensures `import config` / `from services.x import y` resolve regardless of
the directory pytest is invoked from, since this project has no package
__init__.py files (matches the flat folder structure in the README).
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if sys.platform == "win32":
    # Windows' default ProactorEventLoop has a long-standing bug where closing
    # an async HTTP connection's transport after the loop has started shutting
    # down raises "RuntimeError: Event loop is closed" -- observed here with
    # google-genai's async httpx client across multiple sequential test calls.
    # The Selector policy doesn't support subprocesses, which we don't need.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
