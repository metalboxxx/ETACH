"""ETACH sidecar."""

__version__ = "0.6.1"
"""The sidecar's version, built in (step 22.1 answer 18): not read from installed metadata, so a
stale ``etach-<old>.dist-info`` left beside the frozen sidecar cannot show an old version. A test
keeps it equal to ``pyproject.toml``'s ``version``."""
