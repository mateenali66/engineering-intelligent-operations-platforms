"""The guardian: the oversight control plane, the platformized red button.

Google SRE's framework separates the actuation safety-gateway (which validates and
dry-runs every agent action) from the red button (the emergency control that pauses
all in-flight agentic actions, blocks new ones, and can revoke autonomy fleet-wide).
This is the red button. Engage it and every agent on the platform refuses to act
until a human disengages it. Oversight is a first-class control, not an afterthought.
"""

from __future__ import annotations

from agentops.models import Actor


class GuardianPaused(Exception):
    """Raised when an agent tries to act while the red button is engaged."""


class GuardianOverrideDenied(Exception):
    """Raised when a non-human actor tries to engage or release the red button.

    The red button is a human oversight control. Enforcing that only a human can
    flip it is what keeps an agent from pausing a rival or, worse, un-pausing
    itself; the human-only rule lives in code here, not only in a docstring.
    """


class Guardian:
    """A fleet-wide kill switch. One instance is shared by every agent, so a single
    engage() halts all agentic action at once."""

    def __init__(self) -> None:
        self._paused = False

    @property
    def paused(self) -> bool:
        return self._paused

    def engage(self, actor: Actor) -> None:
        """Press the red button: pause all agentic actions across the platform.
        A deliberate human action; a non-human actor is refused."""
        if not actor.is_human:
            raise GuardianOverrideDenied(
                f"{actor.name} is not human; only a human can engage the red button"
            )
        self._paused = True

    def disengage(self, actor: Actor) -> None:
        """Release the red button. A deliberate human action, never an agent's:
        an agent cannot un-pause itself, so a non-human actor is refused."""
        if not actor.is_human:
            raise GuardianOverrideDenied(
                f"{actor.name} is not human; only a human can release the red button"
            )
        self._paused = False

    def assert_clear(self) -> None:
        """Every agent calls this before acting. If the button is engaged, the
        agent cannot proceed, full stop."""
        if self._paused:
            raise GuardianPaused("red button engaged: all agentic actions paused")
