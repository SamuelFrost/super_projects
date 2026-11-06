"""Optional suppression of ADK's experimental UserWarnings.

The filter is off unless a caller passes --hide-experimental-warnings.
The CLI entry point applies it before importing the agents, because those
warnings are emitted while the agents are constructed.
"""

import warnings

HIDE_EXPERIMENTAL_WARNINGS_FLAG = "--hide-experimental-warnings"


def hide_experimental_warnings() -> None:
    """Ignore ADK UserWarnings whose message starts with [EXPERIMENTAL]."""
    warnings.filterwarnings(
        "ignore",
        message=r"^\[EXPERIMENTAL\]",
        category=UserWarning,
    )
