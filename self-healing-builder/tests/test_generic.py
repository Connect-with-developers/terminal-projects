import pytest

# generic test: every generated file must at least import without error
import glob, subprocess, sys, os

def test_generated_files_exist():
    files = glob.glob(os.path.join(os.path.dirname(__file__), "..", "generated", "*.py"))
    assert len(files) >= 1, "No generated files found - run build first"

def test_generated_syntax():
    import py_compile
    import glob, os
    files = glob.glob(os.path.join(os.path.dirname(__file__), "..", "generated", "*.py"))
    for f in files:
        py_compile.compile(f, doraise=True)
