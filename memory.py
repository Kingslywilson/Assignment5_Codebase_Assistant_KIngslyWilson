from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ConversationTurn:
    """Represent one conversation turn."""

    user: str
    assistant: str


@dataclass
class ConversationMemory:
    """
    Store recent conversational history.

    Conversation history provides context for follow-up questions,
    while factual code answers will still be grounded in retrieved
    code from the vector database.
    """

    max_turns: int = 10
    turns: list[ConversationTurn] = field(
        default_factory=list
    )

    def add_turn(
        self,
        user_message: str,
        assistant_message: str,
    ) -> None:
        """Add a completed conversation turn."""

        if not user_message.strip():
            return

        if not assistant_message.strip():
            return

        self.turns.append(
            ConversationTurn(
                user=user_message.strip(),
                assistant=assistant_message.strip(),
            )
        )

        self._trim_history()

    def get_history(self) -> list[dict[str, str]]:
        """
        Return conversation history in a simple
        user/assistant message format.
        """

        history: list[dict[str, str]] = []

        for turn in self.turns:
            history.append(
                {
                    "role": "user",
                    "content": turn.user,
                }
            )

            history.append(
                {
                    "role": "assistant",
                    "content": turn.assistant,
                }
            )

        return history

    def get_formatted_history(self) -> str:
        """
        Return conversation history formatted for use
        in a prompt.
        """

        if not self.turns:
            return "No previous conversation."

        sections = []

        for index, turn in enumerate(
            self.turns,
            start=1,
        ):
            sections.append(
                "\n".join(
                    [
                        f"Conversation Turn {index}",
                        f"User: {turn.user}",
                        f"Assistant: {turn.assistant}",
                    ]
                )
            )

        return "\n\n".join(sections)

    def clear(self) -> None:
        """Clear all conversation history."""

        self.turns.clear()

    def _trim_history(self) -> None:
        """Keep only the most recent configured turns."""

        if self.max_turns <= 0:
            self.turns.clear()
            return

        if len(self.turns) > self.max_turns:
            self.turns = self.turns[
                -self.max_turns:
            ]

    @property
    def turn_count(self) -> int:
        """Return the number of stored conversation turns."""

        return len(self.turns)


def create_memory(
    max_turns: int = 10,
) -> ConversationMemory:
    """Create a conversation memory instance."""

    return ConversationMemory(
        max_turns=max_turns
    )