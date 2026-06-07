"""Configurable edge video analytics framework."""

from .config import load_config
from .pipeline import EdgeVideoPipeline

__all__ = ["EdgeVideoPipeline", "load_config"]

