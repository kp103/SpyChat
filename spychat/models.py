"""Domain models for SpyChat."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import List, Optional


@dataclass
class ChatMessage:
    """A single message exchanged with a friend."""

    message: str
    is_sent_by_me: bool
    time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "message": self.message,
            "is_sent_by_me": self.is_sent_by_me,
            "time": self.time.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ChatMessage":
        return cls(
            message=data["message"],
            is_sent_by_me=data["is_sent_by_me"],
            time=datetime.fromisoformat(data["time"]),
        )


@dataclass
class Spy:
    """A spy: either the current user or a friend."""

    name: str
    salutation: str
    age: int
    rating: float
    is_online: bool = True
    current_status_message: str = "Hey there, I am using SpyChat!"
    chats: List[ChatMessage] = field(default_factory=list)

    @property
    def display_name(self) -> str:
        return f"{self.salutation} {self.name}".strip()

    def to_dict(self) -> dict:
        data = asdict(self)
        data["chats"] = [c.to_dict() for c in self.chats]
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "Spy":
        chats = [ChatMessage.from_dict(c) for c in data.get("chats", [])]
        return cls(
            name=data["name"],
            salutation=data["salutation"],
            age=int(data["age"]),
            rating=float(data["rating"]),
            is_online=data.get("is_online", True),
            current_status_message=data.get(
                "current_status_message", "Hey there, I am using SpyChat!"
            ),
            chats=chats,
        )


@dataclass
class Profile:
    """The persisted state of a SpyChat user: the spy plus their friends."""

    spy: Optional[Spy] = None
    friends: List[Spy] = field(default_factory=list)
    status_messages: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "spy": self.spy.to_dict() if self.spy else None,
            "friends": [f.to_dict() for f in self.friends],
            "status_messages": self.status_messages,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Profile":
        return cls(
            spy=Spy.from_dict(data["spy"]) if data.get("spy") else None,
            friends=[Spy.from_dict(f) for f in data.get("friends", [])],
            status_messages=list(data.get("status_messages", [])),
        )
