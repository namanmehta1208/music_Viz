"""All visualizations. To add one: make a folder here with a Visualization
subclass (see base.py) and list it below. The key is what --viz takes."""

from .aurora import Aurora
from .base import Frame, Visualization
from .fireflies import Fireflies
from .ink import Ink
from .streaks import Streaks
from .tide import Tide

VISUALIZATIONS = {
    "streaks": Streaks,
    "aurora": Aurora,
    "tide": Tide,
    "fireflies": Fireflies,
    "ink": Ink,
}

__all__ = ["VISUALIZATIONS", "Frame", "Visualization"]
