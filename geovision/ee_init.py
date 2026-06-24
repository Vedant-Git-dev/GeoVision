"""Google Earth Engine initialization."""

from __future__ import annotations

import logging
from typing import Optional

import ee

log = logging.getLogger(__name__)


def init_ee(project: Optional[str]) -> None:
    """Initialize Earth Engine, prompting for auth if needed."""
    kwargs = {"project": project} if project else {}
    try:
        ee.Initialize(**kwargs)
        log.info("EE initialised (project=%s)", project or "<default>")
    except ee.EEException:
        log.info("Launching EE auth in browser...")
        ee.Authenticate()
        ee.Initialize(**kwargs)
