# Codebase Assistant Strategy

## 1. Objective

The Codebase Assistant is a conversational code intelligence system built with Python and LangChain.

Its purpose is to ingest Python and JavaScript projects, understand their structure and source code, index the code semantically, and answer developer questions using Retrieval-Augmented Generation (RAG).

The system is designed so that factual answers are grounded in the indexed source code rather than relying only on the language model's general knowledge.

---

## 2. Overall RAG Architecture

The system follows this pipeline:

```text
Project
   |
   v
Code Ingestion
   |
   v
File Filtering
   |
   v
Python / JavaScript Parsing
   |
   v
Logical Code Documents
   |
   v
Code-Aware Chunking
   |
   v
Embeddings
   |
   v
FAISS Vector Database
   |
   v
LangChain Retriever
   |
   v
Relevant Code Context
   |
   v
Prompt + Conversation Context
   |
   v
Groq LLM
   |
   v
Grounded Answer
   |
   v
Source References
```

---

## 3. Code Ingestion Strategy

The `CodebaseLoader` recursively scans a selected project directory.

Supported primary source files:

* `.py`
* `.js`

Additional supported text files:

* `.json`
* `.md`
* `.txt`
* `.yaml`
* `.yml`

Each indexed file is represented using metadata including:

* Absolute path
* Relative path
* File name
* Language
* Module
* File type

Relative paths are used as source references so that answers can identify where relevant code is located.

---

## 4. File and Secret Filtering

The loader excludes directories that normally contain generated files, dependencies, caches, or development tooling.

Ignored directories include:

```text
.git
__pycache__
venv
.venv
node_modules
dist
build
coverage
.pytest_cache
.idea
.vscode
```

Sensitive files are excluded, including:

```text
.env
.env.local
.env.development
.env.production
credentials.json
secrets.json
*.pem
*.key
```

Other generated or binary files are also excluded where appropriate.

The objective is to prevent unnecessary files and sensitive configuration from entering the retrieval pipeline.

---

## 5. Code Parsing

### Python Parsing

Python source code is parsed using the standard Python AST module.

The parser extracts:

* Imports
* Functions
* Async functions
* Classes
* Parameters
* Signatures
* Docstrings
* Parent classes
* Source line ranges
* Route information when detectable

AST parsing provides structural information instead of treating Python code as unstructured text.

### JavaScript Parsing

JavaScript source code is parsed using Tree-sitter when available.

The parser extracts:

* Imports
* Required modules
* Functions
* Classes
* Methods
* Source locations
* Express-style routes when detectable

A fallback parser is used when Tree-sitter parsing is unavailable or cannot parse a particular source file.

---

## 6. Code-Aware Chunking

The preprocessing stage converts parsed source code into LangChain `Document` objects.

The system attempts to preserve logical code units such as:

* Functions
* Classes
* Methods
* Route handlers
* Related source sections

The default chunking configuration is:

```text
Chunk size: 1200 characters
Chunk overlap: 150 characters
```

Large logical code units are recursively split using a LangChain text splitter.

This approach provides more meaningful retrieval context than blindly splitting source files into fixed-size blocks.

---

## 7. Metadata Strategy

Each generated document contains metadata such as:

```text
source
file_name
language
module
file_type
symbol
symbol_type
signature
parameters
parent
start_line
end_line
docstring
route
http_method
imports
```

Metadata is important because it allows retrieved results to be converted into useful source references.

For example:

```text
app/services/auth_service.py
authenticate_user()
lines 4-17
```

This makes the generated answer traceable to the indexed project.

---

## 8. Embedding Strategy

The system uses Hugging Face Sentence Transformers for semantic embeddings.

Default model:

```text
sentence-transformers/all-MiniLM-L6-v2
```

Embeddings are normalized before indexing.

The purpose of embeddings is to represent code and questions in a semantic vector space so that conceptually relevant code can be retrieved even when the question does not use exactly the same wording as the source code.

---

## 9. Vector Database

FAISS is used as the vector database.

The workflow is:

```text
Code Documents
      |
      v
Embeddings
      |
      v
FAISS Index
```

The FAISS index can be saved locally and loaded again for the indexed project.

The vector index is treated as application-generated data and is excluded from source-control submission where appropriate.

---

## 10. Retrieval Strategy

The assistant uses a LangChain retriever over the FAISS vector store.

The default retrieval configuration uses:

```text
Top K = 5
```

The retriever returns the most semantically relevant code documents for a user query.

Each result retains its original metadata so that the answer can include file and line references.

---

## 11. Conversational Memory

The assistant maintains a bounded conversation history.

The current memory configuration stores up to:

```text
10 conversation turns
```

Conversation history is used to understand follow-up questions.

For example:

```text
User:
How does login work?

Assistant:
...

User:
Where is the password verified?
```

The second question can use the previous conversation to understand that the user is referring to the login flow.

However, conversation history is not treated as the authoritative source for code facts.

The assistant performs retrieval again for factual follow-up questions.

---

## 12. Prompt Grounding

The main QA prompt instructs the language model to:

1. Use retrieved source code as factual evidence.
2. Avoid inventing files, functions, classes, APIs, dependencies, or execution paths.
3. Avoid claiming project behavior without supporting source code.
4. Identify relevant files and functions.
5. Follow cross-file relationships only when supported by retrieved code.
6. Distinguish confirmed behavior from possible behavior.
7. Retrieve code again for factual follow-up questions.
8. Avoid exposing secrets or credentials.

If the retrieved context does not contain enough information, the assistant should respond:

```text
This information is not available in the indexed codebase.
```

---

## 13. Code Explanation Strategy

Code explanation requests use a specialized prompt.

The response should identify:

* Relevant file
* Relevant function or class
* Parameters
* Return values
* Important logic
* Calls to other functions
* Cross-file relationships

The explanation distinguishes between:

```text
Confirmed behavior
```

and:

```text
Possible behavior
```

This prevents unsupported assumptions from being presented as facts.

---

## 14. Bug Analysis Strategy

Bug investigation uses a dedicated bug-analysis prompt.

Each finding is classified as:

### CONFIRMED

The indexed source code directly supports the finding.

### POSSIBLE

The source code suggests a potential issue, but additional runtime or external evidence is required.

### NOT ENOUGH INFORMATION

The indexed code does not contain enough evidence to determine whether the issue exists.

The assistant must not claim a bug is confirmed without supporting source-code evidence.

---

## 15. Architecture Analysis Strategy

Architecture questions use a dedicated architecture prompt.

The assistant analyzes:

* Entry points
* Modules
* Components
* Layers
* Imports
* Dependencies
* Responsibilities
* Data flow
* Authentication/security flow
* Cross-file relationships
* Execution paths

Relationships should be identified using actual source files and functions retrieved from the indexed project.

Unsupported architecture assumptions should not be presented as confirmed facts.

---

## 16. Documentation Generation

The system provides three documentation generators.

### README Generator

Uses retrieved code to generate:

```text
outputs/generated_README.md
```

The generated README can include:

* Project overview
* Features
* Project structure
* Technologies
* Dependencies
* Entry points
* Supported setup information
* Supported usage information

Only information supported by the indexed code should be included.

### API Documentation Generator

Generates:

```text
outputs/api_documentation.md
```

The documentation focuses on:

* Routes
* HTTP methods
* Functions
* Parameters
* Authentication behavior
* Responses
* Source files

Unsupported APIs must not be invented.

### Architecture Documentation Generator

Generates:

```text
outputs/architecture_summary.md
```

It focuses on:

* Entry points
* Components
* Modules
* Dependencies
* Import relationships
* Data flow
* Security flow
* Cross-file execution paths

---

## 17. Source References

Retrieved documents preserve source metadata.

The application uses this information to display references such as:

```text
Source: app/api/auth.py
Function: login
Lines: 3-12
```

Source references provide traceability between an answer and the indexed project.

---

## 18. Streaming Strategy

The assistant uses the Groq chat model through LangChain.

For normal chat questions, response tokens are streamed to the Streamlit interface.

This provides incremental output instead of waiting for the complete response before displaying anything.

The complete streamed response is retained so that it can be stored in conversation memory.

---

## 19. Token Tracking

The monitori
