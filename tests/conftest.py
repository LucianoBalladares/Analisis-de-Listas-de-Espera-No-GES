"""
conftest.py — pytest configuration for the pipeline test suite.

Adds the project root to sys.path so that `pipeline.*` imports resolve
without requiring an editable install.
"""
import sys
from pathlib import Path

# Insert project root (parent of tests/) at the front of sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))