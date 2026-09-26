# Conversational Codebase Assistant

A Python and LangChain based Codebase Intelligence Assistant that indexes Python and JavaScript projects and provides grounded conversational answers about the source code.

## Features

* Ingests Python and JavaScript source code
* Supports optional `.json`, `.md`, `.txt`, `.yaml`, and `.yml` files
* Excludes common generated, dependency, cache, and secret files
* Parses Python using Python AST
* Parses JavaScript using Tree-sitter with a fallback parser
* Extracts functions, classes, imports, parameters, routes, and source locations
* Creates code-aware chunks with source metadata
* Generates semantic embeddings using Sentence Transformers
* Stores embeddings in a FAISS vector database
* Uses a LangChain retriever for semantic code search
* Answers questions using Groq LLMs
* Provides source file and line references
* Supports multi-turn conversational context
* Supports code explanation
* Supports bug analysis with confirmed/possible classifications
* Supports architecture analysis
* Generates project README documentation
* Generates API documentation
* Generates architecture documentation
* Supports streamed responses
* Tracks token usage
* Supports LangSmith tracing
* Includes hallucination prevention and unavailable-information handling

## Project Structure

```text
Assignment5_Codebase_Assistant/
│
├── app.py
├── code_loader.py
├── code_parser.py
├── preprocess.py
├── vector_store.py
├── retriever.py
├── qa_chain.py
├── memory.py
├── monitoring.py
│
├── documentation/
│   ├── __init__.py
│   ├── readme_generator.py
│   ├── api_doc_generator.py
│   └── architecture_generator.py
│
├── prompts/
│   ├── code_qa_prompt.txt
│   ├── code_explanation_prompt.txt
│   ├── bug_analysis_prompt.txt
│   ├── architecture_prompt.txt
│   ├── readme_prompt.txt
│   ├── api_documentation_prompt.txt
│   └── architecture_documentation_prompt.txt
│
├── sample_projects/
│   ├── python_project/
│   └── javascript_project/
│
├── outputs/
│
├── codebase_assistant_strategy.md
├── test_log.md
├── README.md
├── requirements.txt
├── .env.example
└── .gitignore
```

## Technologies

* Python
* LangChain
* LangChain Community
* LangChain Groq
* LangChain Hugging Face
* FAISS
* Sentence Transformers
* Tree-sitter
* Streamlit
* Groq
* LangSmith
* Pydantic
* python-dotenv

## Architecture

The application follows this general flow:

```text
Project Folder / ZIP Upload
          |
          v
     Code Loader
          |
          v
     Code Parser
          |
          v
   Code Preprocessor
          |
          v
    Code Documents
          |
          v
    Hugging Face
     Embeddings
          |
          v
      FAISS Index
          |
          v
   LangChain Retriever
          |
          v
      Code Context
          |
          v
      Groq LLM
          |
          v
 Conversational Answer
          |
          v
 Source References
```

## Code Ingestion

The assistant indexes supported source files while excluding files and directories that should not be part of the codebase knowledge.

Ignored directories include:

* `.git`
* `__pycache__`
* `venv`
* `.venv`
* `node_modules`
* `dist`
* `build`
* `coverage`
* `.pytest_cache`
* `.idea`
* `.vscode`

Sensitive files such as `.env`, credentials files, secret files, private keys, and certificates are excluded from indexing.

## Supported File Types

The primary supported source languages are:

* `.py`
* `.js`

Additional text-based files supported by the loader include:

* `.json`
* `.md`
* `.txt`
* `.yaml`
* `.yml`

## Code Parsing

### Python

Python source files are parsed using the Python `ast` module.

The parser extracts information such as:

* Imports
* Functions
* Async functions
* Classes
* Function parameters
* Signatures
* Docstrings
* Parent classes
* Source line ranges
* Route information when supported

### JavaScript

JavaScript files are parsed using Tree-sitter when available.

The parser extracts information such as:

* Imports
* Required modules
* Functions
* Classes
* Methods
* Source locations
* Express-style route information when detectable

A fallback parser is available when Tree-sitter parsing cannot be used.

## Code-Aware Chunking

Source code is converted into LangChain `Document` objects.

The preprocessing stage attempts to preserve logical code units such as functions and classes rather than treating the entire project as one text block.

Each document contains metadata such as:

* Source path
* File name
* Language
* Module
* Symbol name
* Symbol type
* Function signature
* Parameters
* Parent class
* Start line
* End line
* Imports
* Route information

## Vector Search

The assistant uses:

```text
Sentence Transformers
        |
        v
Hugging Face Embeddings
        |
        v
FAISS
        |
        v
LangChain Retriever
```

The default embedding model is:

```text
sentence-transformers/all-MiniLM-L6-v2
```

The retriever uses semantic similarity to find relevant code before sending context to the language model.

## Conversational Question Answering

The assistant supports questions such as:

* Explain this function.
* What does this class do?
* How does login work?
* Trace the authentication flow.
* Which files are involved when a user logs in?
* Where is the password verified?
* How is the access token created?
* What could cause this function to fail?
* Explain the architecture of this project.

The assistant retrieves code again for factual follow-up questions instead of relying only on conversation memory.

## Hallucination Prevention

The assistant follows strict grounding rules.

It should:

* Use indexed source code as the factual evidence.
* Avoid inventing files or functions.
* Avoid inventing APIs or dependencies.
* Avoid inventing execution paths.
* Distinguish confirmed behavior from possible behavior.
* Provide source references when available.

When the indexed code does not contain enough information, the assistant uses:

> This information is not available in the indexed codebase.

Bug analysis uses the following classifications:

* `CONFIRMED`
* `POSSIBLE`
* `NOT ENOUGH INFORMATION`

## Source References

Answers can identify the relevant:

* File path
* Function
* Class
* Source line range

This allows users to trace an answer back to the indexed code.

## Documentation Generation

The application provides three documentation generators.

### README

Generates:

```text
outputs/generated_README.md
```

### API Documentation

Generates:

```text
outputs/api_documentation.md
```

### Architecture Summary

Generates:

```text
outputs/architecture_summary.md
```

Generated documentation is instructed to use only information supported by the indexed codebase.

## Streaming

Chat responses are streamed to the Streamlit interface so that generated responses can be displayed progressively.

## Token Tracking

The application includes a usage tracker for:

* Input tokens
* Output tokens
* Total tokens

The Streamlit interface displays the collected token usage.

## LangSmith Tracing

LangSmith tracing can be enabled through environment variables.

Configure:

```env
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=your_langsmith_api_key_here
LANGSMITH_PROJECT=codebase-assistant
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
```

Do not commit actual API keys.

## Environment Setup

Create and activate a virtual environment.

### Windows PowerShell

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and configure the required API keys.

The actual `.env` file must not be included in the submission ZIP.

## Running the Application

From the project directory:

```powershell
streamlit run app.py
```

The Streamlit interface provides:

* Project indexing
* Conversational chat
* Code intelligence analysis
* Documentation generation
* Indexed project file inspection
* Token usage information

## Sample Projects

Two sample projects are included for evaluation:

```text
sample_projects/python_project/
sample_projects/javascript_project/
```

The Python sample demonstrates:

* Application entry point
* Authentication route
* User creation
* Authentication service
* User service
* Password hashing
* Token generation
* Database operations

The JavaScript sample provides an equivalent multi-file authentication flow.

## Security

The assistant is designed to avoid indexing common secret and credential files.

The project excludes:

* `.env`
* `.env.local`
* `credentials.json`
* `secrets.json`
* `.pem`
* `.key`

API keys and credentials must never be placed directly into source files, prompts, logs, generated documentation, or the submission ZIP.

## Testing

Testing will cover:

* Python project ingestion
* JavaScript project ingestion
* Ignored files and directories
* Empty projects
* Code explanation
* Cross-file execution tracing
* Bug analysis
* Architecture analysis
* Unavailable information
* Multi-turn follow-up questions
* README generation
* API documentation generation
* Architecture summary generation
* Streaming
* Token tracking
* LangSmith tracing

Actual test results will be recorded in:

```text
test_log.md
```

## Submission

The final submission should be packaged as:

```text
Assignment5_Codebase_Assistant_<YourName>.zip
```

The ZIP should contain the complete source code, prompts, sample projects, generated documentation, strategy document, test log, README, requirements, and `.env.example`.

The following must not be included:

* `.env`
* API keys
* credentials
* virtual environments
* `node_modules`
* cache directories
* generated model files
* unauthorized third-party code
