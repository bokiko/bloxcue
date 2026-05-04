import os
import tempfile
from pathlib import Path


_ROOT = Path(tempfile.mkdtemp(prefix="bloxcue-tests-"))
_KNOWLEDGE = _ROOT / "knowledge"
_KNOWLEDGE.mkdir(parents=True, exist_ok=True)
(_KNOWLEDGE / "guides").mkdir(exist_ok=True)
(_KNOWLEDGE / "guides" / "deployment.md").write_text(
    """---
title: Deployment Guide
category: guides
tags: [deployment, production]
---

# Deployment Guide

Deploy production changes by running tests, applying migrations, and restarting services.
""",
    encoding="utf-8",
)

os.environ.setdefault("BLOXCUE_MEMORY_DIR", str(_KNOWLEDGE))
os.environ.setdefault("BLOXCUE_LEARNINGS_DB", str(_ROOT / "learnings.db"))
