"""CP-58: static scanner for quarantined third-party skills.

Never imports or executes scanned code. Findings carry rule, severity, line.
Verdict: block (critical/high), review (medium), pass.
"""
from __future__ import annotations

import ast
import os
import re
from typing import Any, Dict, List

HIGH_IMPORTS = {"subprocess", "socket", "ctypes", "pty", "multiprocessing"}
NET_IMPORTS = {"requests", "urllib", "urllib3", "http", "httpx", "aiohttp", "ftplib", "smtplib"}
CRITICAL_CALLS = {"eval", "exec", "compile", "__import__"}
OS_DANGEROUS = {"system", "popen", "execv", "execve", "execl", "spawnl", "spawnv", "remove", "rmdir"}
SHUTIL_DANGEROUS = {"rmtree"}
BLOB_RE = re.compile(r"[A-Za-z0-9+/=]{200,}")
SECRET_RE = re.compile(
    r"(sk-[A-Za-z0-9_-]{16,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{20,}"
    r"|-----BEGIN [A-Z ]*PRIVATE KEY-----)"
)
SHELL_PATTERNS = re.compile(
    r"(curl|wget)\s+[^|\n]*\|\s*(sh|bash)|pip3?\s+install|Invoke-Expression|iex\s*\(|"
    r"Invoke-WebRequest|rm\s+-rf\s+/|powershell\s+-enc", re.IGNORECASE)
MAX_FILE = 1_000_000
MAX_FILES = 500
SCRIPT_EXT = {".sh", ".ps1", ".bat", ".cmd", ".js", ".vbs"}


def _f(rule: str, severity: str, line: int, file: str = "") -> Dict[str, Any]:
    return {"rule": rule, "severity": severity, "line": line, "file": file}


def scan_source(source: str, filename: str = "") -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        findings.append(_f("unparseable_python", "high", 1, filename))
        tree = None

    if tree is not None:
        for node in ast.walk(tree):
            line = getattr(node, "lineno", 0)
            if isinstance(node, ast.Import):
                names = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [(node.module or "").split(".")[0]]
            else:
                names = []
            for n in names:
                if n in HIGH_IMPORTS:
                    findings.append(_f(f"import_{n}", "high", line, filename))
                elif n in NET_IMPORTS:
                    findings.append(_f(f"network_import_{n}", "medium", line, filename))
            if isinstance(node, ast.Call):
                fn = node.func
                if isinstance(fn, ast.Name) and fn.id in CRITICAL_CALLS:
                    findings.append(_f(f"call_{fn.id}", "critical", line, filename))
                elif isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name):
                    if fn.value.id == "os" and fn.attr in OS_DANGEROUS:
                        findings.append(_f(f"os_{fn.attr}", "high", line, filename))
                    elif fn.value.id == "shutil" and fn.attr in SHUTIL_DANGEROUS:
                        findings.append(_f("shutil_rmtree", "high", line, filename))
                    elif fn.value.id == "subprocess":
                        findings.append(_f(f"subprocess_{fn.attr}", "high", line, filename))
                elif isinstance(fn, ast.Name) and fn.id == "open" and len(node.args) >= 2:
                    mode = node.args[1]
                    if isinstance(mode, ast.Constant) and isinstance(mode.value, str) \
                            and any(c in mode.value for c in "wax+"):
                        findings.append(_f("file_write", "medium", line, filename))

    for i, text in enumerate(source.splitlines(), 1):
        if SECRET_RE.search(text):
            findings.append(_f("hardcoded_secret", "high", i, filename))
        if BLOB_RE.search(text):
            findings.append(_f("encoded_blob", "medium", i, filename))
        if SHELL_PATTERNS.search(text):
            findings.append(_f("shell_install_or_download", "high", i, filename))
    return findings


def scan_tree(root: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    count = 0
    for base, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = [d for d in dirs if d not in (".git", "__pycache__")]
        for name in sorted(files):
            path = os.path.join(base, name)
            rel = os.path.relpath(path, root)
            count += 1
            if count > MAX_FILES:
                findings.append(_f("too_many_files", "high", 0, rel))
                return findings
            if os.path.islink(path):
                findings.append(_f("symlink", "high", 0, rel))
                continue
            if os.path.getsize(path) > MAX_FILE:
                findings.append(_f("file_too_large", "medium", 0, rel))
                continue
            ext = os.path.splitext(name)[1].lower()
            if ext == ".py":
                with open(path, "r", encoding="utf-8", errors="replace") as handle:
                    findings += scan_source(handle.read(), rel)
            elif ext in SCRIPT_EXT:
                findings.append(_f("non_python_script", "medium", 0, rel))
                with open(path, "r", encoding="utf-8", errors="replace") as handle:
                    for i, text in enumerate(handle.read().splitlines(), 1):
                        if SHELL_PATTERNS.search(text):
                            findings.append(_f("shell_install_or_download", "high", i, rel))
    return findings


def verdict(findings: List[Dict[str, Any]]) -> str:
    severities = {f["severity"] for f in findings}
    if severities & {"critical", "high"}:
        return "block"
    if "medium" in severities:
        return "review"
    return "pass"