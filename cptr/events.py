"""Application event definitions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EventDefinition:
    name: str
    label: str


class EventDefinitions:
    CHAT_FINISHED = EventDefinition("chat.finished", "Chat finished")
    CHAT_FAILED = EventDefinition("chat.failed", "Chat failed")
    NOTIFICATION_TEST = EventDefinition("notification.test", "Test notification")
    NOTIFICATION_MANUAL = EventDefinition("manual.notify", "Notification")


EVENTS = EventDefinitions()

CHAT_NOTIFICATION_EVENTS = (
    EVENTS.CHAT_FINISHED,
    EVENTS.CHAT_FAILED,
)
