from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator
import os

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

from memory import ConversationMemory
from monitoring import extract_token_usage
from retriever import CodeRetriever, RetrievedCode


BASE_DIR = Path(__file__).resolve().parent
PROMPTS_DIR = BASE_DIR / "prompts"

DEFAULT_MODEL = os.getenv(
    "GROQ_MODEL",
    "openai/gpt-oss-120b",
)


@dataclass
class QAResponse:
    """Represent a grounded codebase answer."""

    answer: str
    sources: list[RetrievedCode]
    query: str


class CodeQAChain:
    """Conversational RAG chain for source-code questions."""

    FALLBACK_MESSAGE = (
        "This information is not available in the indexed codebase."
    )

    def __init__(
        self,
        retriever: CodeRetriever,
        memory: ConversationMemory,
        model_name: str = DEFAULT_MODEL,
        temperature: float = 0.0,
        usage_tracker=None,
    ):
        self.retriever = retriever
        self.memory = memory
        self.usage_tracker = usage_tracker

        self.llm = ChatGroq(
            model=model_name,
            temperature=temperature,
        )

        self.system_prompt = self._load_prompt(
            "code_qa_prompt.txt"
        )

    # ---------------------------------------------------------
    # RETRIEVAL QUERY
    # ---------------------------------------------------------

    def _build_retrieval_query(self, query: str) -> str:
        """
        Build a retrieval query that can resolve conversational
        follow-up questions such as:
        "What file is that function defined in?"
        """

        query = query.strip()

        if self.memory.turn_count <= 0:
            return query

        recent_turn = self.memory.turns[-1]

        previous_user = recent_turn.user.strip()

        # Keep previous assistant context bounded so that very long
        # answers do not unnecessarily expand the retrieval query.
        previous_assistant = recent_turn.assistant.strip()[:2000]

        return (
            "Previous user question:\n"
            f"{previous_user}\n\n"
            "Previous assistant answer:\n"
            f"{previous_assistant}\n\n"
            "Current question:\n"
            f"{query}"
        )

    # ---------------------------------------------------------
    # NORMAL QUESTION ANSWERING
    # ---------------------------------------------------------

    def ask(self, query: str) -> QAResponse:
        """Answer a codebase question using retrieved context."""

        query = query.strip()

        if not query:
            raise ValueError("Question cannot be empty.")

        retrieval_query = self._build_retrieval_query(query)

        results, context = self.retriever.retrieve_context(
            retrieval_query
        )

        if not results:
            answer = self.FALLBACK_MESSAGE

            self.memory.add_turn(
                query,
                answer,
            )

            return QAResponse(
                answer=answer,
                sources=[],
                query=query,
            )

        messages = self._build_messages(
            query=query,
            context=context,
        )

        response = self.llm.invoke(messages)

        self._record_usage(response)

        answer = self._extract_response_text(response)

        if not answer.strip():
            answer = self.FALLBACK_MESSAGE

        self.memory.add_turn(
            query,
            answer,
        )

        return QAResponse(
            answer=answer,
            sources=results,
            query=query,
        )

    # ---------------------------------------------------------
    # SPECIALIZED QUESTIONS
    # ---------------------------------------------------------

    def explain_code(self, query: str) -> QAResponse:
        """Explain source code using retrieved code context."""

        return self._specialized_query(
            query=query,
            prompt_file="code_explanation_prompt.txt",
        )

    def analyze_bug(self, query: str) -> QAResponse:
        """Investigate a possible bug using retrieved code."""

        return self._specialized_query(
            query=query,
            prompt_file="bug_analysis_prompt.txt",
        )

    def analyze_architecture(self, query: str) -> QAResponse:
        """Analyze project architecture using retrieved code."""

        return self._specialized_query(
            query=query,
            prompt_file="architecture_prompt.txt",
        )

    def _specialized_query(
        self,
        query: str,
        prompt_file: str,
    ) -> QAResponse:
        """Execute a specialized grounded analysis."""

        query = query.strip()

        if not query:
            raise ValueError("Question cannot be empty.")

        retrieval_query = self._build_retrieval_query(query)

        results, context = self.retriever.retrieve_context(
            retrieval_query
        )

        if not results:
            answer = self.FALLBACK_MESSAGE

            self.memory.add_turn(
                query,
                answer,
            )

            return QAResponse(
                answer=answer,
                sources=[],
                query=query,
            )

        prompt = self._load_prompt(prompt_file)

        history = self.memory.get_formatted_history()

        user_prompt = f"""
CONVERSATION HISTORY:

{history}

RETRIEVED CODE:

{context}

REQUEST:

{query}

GROUNDING RULES:

1. Use the retrieved code as the only factual source.

2. Do not invent files, functions, classes, APIs, dependencies,
   execution paths, or behavior.

3. Do not use outside knowledge as evidence about this project.

4. If the retrieved code does not contain enough evidence,
   respond with:

"{self.FALLBACK_MESSAGE}"

5. When describing a function or module, identify only files
   and symbols actually present in the retrieved code.
"""

        messages = [
            SystemMessage(content=prompt),
            HumanMessage(content=user_prompt),
        ]

        response = self.llm.invoke(messages)

        self._record_usage(response)

        answer = self._extract_response_text(response)

        if not answer.strip():
            answer = self.FALLBACK_MESSAGE

        self.memory.add_turn(
            query,
            answer,
        )

        return QAResponse(
            answer=answer,
            sources=results,
            query=query,
        )

    # ---------------------------------------------------------
    # STREAMING
    # ---------------------------------------------------------

    def stream(self, query: str) -> Iterator[str]:
        """Stream a grounded answer from the Groq model."""

        query = query.strip()

        if not query:
            raise ValueError("Question cannot be empty.")

        retrieval_query = self._build_retrieval_query(query)

        results, context = self.retriever.retrieve_context(
            retrieval_query
        )

        if not results:
            answer = self.FALLBACK_MESSAGE

            self.memory.add_turn(
                query,
                answer,
            )

            yield answer
            return

        messages = self._build_messages(
            query=query,
            context=context,
        )

        collected: list[str] = []
        last_chunk = None

        for chunk in self.llm.stream(messages):
            last_chunk = chunk

            text = self._extract_response_text(chunk)

            if text:
                collected.append(text)
                yield text

        # Some LangChain/Groq versions expose usage only on the
        # final streamed chunk.
        if last_chunk is not None:
            self._record_usage(last_chunk)

        complete_answer = "".join(collected).strip()

        if not complete_answer:
            complete_answer = self.FALLBACK_MESSAGE

        self.memory.add_turn(
            query,
            complete_answer,
        )

    # ---------------------------------------------------------
    # MESSAGE BUILDING
    # ---------------------------------------------------------

    def _build_messages(
        self,
        query: str,
        context: str,
    ):
        """Build the LLM message sequence."""

        history = self.memory.get_formatted_history()

        user_prompt = f"""
CONVERSATION HISTORY:

{history}

RETRIEVED CODE CONTEXT:

{context}

CURRENT QUESTION:

{query}

INSTRUCTIONS:

Answer the current question using the retrieved
code context as the factual source.

Conversation history may help resolve references such
as "it", "that function", or "where is this called",
but do not use conversation history as a substitute
for retrieved code.

If the retrieved code does not contain enough evidence
to answer the question, say:

"{self.FALLBACK_MESSAGE}"

Do not invent files, functions, classes, APIs,
dependencies, execution paths, or behavior.

When explaining an execution flow, identify the actual
files and functions found in the retrieved code.
"""

        return [
            SystemMessage(
                content=self.system_prompt
            ),
            HumanMessage(
                content=user_prompt
            ),
        ]

    # ---------------------------------------------------------
    # TOKEN USAGE
    # ---------------------------------------------------------

    def _record_usage(self, response) -> None:
        """Record token usage from a model response safely."""

        if self.usage_tracker is None:
            return

        try:
            usage = extract_token_usage(response)
        except Exception:
            # Usage information should never break a valid answer.
            return

        if usage is None:
            return

        input_tokens = 0
        output_tokens = 0

        # Current monitoring.py returns:
        # (input_tokens, output_tokens)
        if isinstance(usage, tuple):

            if len(usage) >= 2:
                input_tokens = usage[0] or 0
                output_tokens = usage[1] or 0

        # Also support dictionary-shaped usage information.
        elif isinstance(usage, dict):

            input_tokens = (
                usage.get("input_tokens")
                or usage.get("prompt_tokens")
                or 0
            )

            output_tokens = (
                usage.get("output_tokens")
                or usage.get("completion_tokens")
                or 0
            )

        try:
            self.usage_tracker.record(
                input_tokens=int(input_tokens),
                output_tokens=int(output_tokens),
            )
        except Exception:
            pass

    # ---------------------------------------------------------
    # RESPONSE TEXT
    # ---------------------------------------------------------

    @staticmethod
    def _extract_response_text(response) -> str:
        """Extract text from an AI message or streamed chunk."""

        content = getattr(
            response,
            "content",
            response,
        )

        if isinstance(content, str):
            return content

        if isinstance(content, list):

            parts = []

            for item in content:

                if isinstance(item, str):
                    parts.append(item)

                elif isinstance(item, dict):

                    text = item.get("text")

                    if text:
                        parts.append(str(text))

            return "".join(parts)

        return str(content)

    # ---------------------------------------------------------
    # PROMPT LOADING
    # ---------------------------------------------------------

    @staticmethod
    def _load_prompt(filename: str) -> str:
        """Load a prompt from the prompts directory."""

        prompt_path = PROMPTS_DIR / filename

        if not prompt_path.exists():
            raise FileNotFoundError(
                f"Prompt file not found: {prompt_path}"
            )

        return prompt_path.read_text(
            encoding="utf-8"
        ).strip()


def create_qa_chain(
    retriever: CodeRetriever,
    memory: ConversationMemory,
    model_name: str = DEFAULT_MODEL,
    temperature: float = 0.0,
    usage_tracker=None,
) -> CodeQAChain:
    """Create the conversational QA chain."""

    return CodeQAChain(
        retriever=retriever,
        memory=memory,
        model_name=model_name,
        temperature=temperature,
        usage_tracker=usage_tracker,
    )