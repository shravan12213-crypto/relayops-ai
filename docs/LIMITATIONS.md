# RelayOps Honest Engineering Limitations & Future Roadmap

In the spirit of rigorous software engineering and transparent evaluation, this document outlines known architectural boundaries, operational limitations, and planned enhancements for RelayOps.

---

## 1. Database & Concurrency Scaling (SQLite vs PostgreSQL)

### Current Architecture
RelayOps utilizes **SQLite with Write-Ahead Logging (WAL)**, foreign key constraints enabled, and a 5,000ms busy timeout. SQLite delivers zero operational overhead, single-file portability, and ACID reliability. Full-text search is powered by native SQLite FTS5 with BM25 ranking.

### Known Limitations
- **Write Serialization:** SQLite supports unlimited concurrent readers, but serializes write transactions through a database-level lock. For small-to-medium development teams and standard handover workloads (hundreds to tens of thousands of artifacts), this performs under 5ms per write. However, under high-concurrency enterprise workloads with hundreds of simultaneous write streams, write contention can lead to `busy_timeout` exceptions.
- **Single-Host Bound:** SQLite cannot scale horizontally across a distributed multi-node cluster without distributed storage overlays (e.g. Litestream, LiteFS).

### Production Roadmap
For enterprise multi-tenant deployments, the persistence layer can be migrated to **PostgreSQL with pgvector and pg_trgm** using standard SQLModel/SQLAlchemy engine configurations, maintaining the identical schema and business logic.

---

## 2. Identity, Authentication & Directory Services

### Current Architecture
RelayOps implements secure built-in authentication using:
- **Password Hashing:** Python standard library `hashlib.scrypt` with unique salt per user and work factors $N=16384, r=8, p=1$.
- **Session Tokens:** Cryptographic JWT tokens (HS256) stored in `httpOnly`, `SameSite=Lax` browser cookies and returned for API clients.
- **RBAC / ABAC:** Role and clearance enforcement via `backend/app/policy.py`.

### Known Limitations
- **No Enterprise SSO / SAML 2.0 / OIDC:** RelayOps does not currently integrate natively with identity providers like Okta, Google Workspace, Azure AD, or Keycloak. Users must be provisioned via the database or seed scripts.
- **No Multi-Factor Authentication (MFA/TOTP):** RelayOps currently relies on single-factor password authentication.
- **In-Memory Rate Limiting:** Login rate limiting (10 attempts/min/IP) is held in application memory, which resets upon container restarts.

### Production Roadmap
Implement OAuth2 / OpenID Connect (OIDC) endpoints enabling federated Single Sign-On (SSO) with enterprise identity providers.

---

## 3. Redaction Engine Scope & DLP Boundaries

### Current Architecture
RelayOps features a dependency-free, high-speed redaction engine in `backend/app/ingest/redact.py` that combines:
- **Shannon Entropy Token Detection:** Identifies arbitrary high-entropy random keys ($\ge 16$ chars, $> 3.2 \text{ bits/symbol}$).
- **Deterministic Pattern Matchers:** Covers AWS keys, Stripe secret keys, GitHub PATs, Bearer tokens, private keys, connection strings, emails, phone numbers, and compensation figures.

### Known Limitations
- **Evasion via Deliberate Obfuscation:** A malicious developer deliberately obfuscating secrets (e.g., splitting a secret across multiple lines, base64-encoding an encrypted payload, or using steganographic spacing) can evade regex and entropy detectors.
- **Contextual PII / NER:** The regex engine identifies structured PII (emails, phone numbers, salary markers), but does not perform full Natural Language Named Entity Recognition (NER) for arbitrary personal names or unformatted home addresses without external machine learning models (such as Microsoft Presidio or spaCy).
- **False Positives on Code Hashes:** High-entropy git commit SHAs or cryptographic checksums can occasionally trigger the entropy detector if not preceded by known commit identifiers.

### Production Roadmap
Provide an optional pluggable backend for enterprise Data Loss Prevention (DLP) services (e.g., Google Cloud DLP or AWS Macie) for organizations with strict regulatory scanning mandates.

---

## 4. LLM Non-Determinism & Provider Dependency

### Current Architecture
RelayOps supports dual operation modes:
- **Replay Mode (Default / Offline):** Deterministic evaluation using cached LLM outputs stored in `backend/seed/llm_recordings.json`. Runs with zero network connectivity and zero API keys.
- **Live Mode:** Connects to OpenAI (`gpt-4o-mini`) or Anthropic (`claude-3-5-sonnet`) with strict JSON-schema output enforcement and post-generation citation validation.

### Known Limitations
- **LLM Output Drift:** In Live Mode, frontier LLMs can occasionally alter sentence phrasing or extraction granularity even at `temperature=0.0`. While RelayOps enforces schema validation and drops ungrounded claims, minor variations in extracted claim counts can occur between model versions.
- **Rate Limits & Latency:** In Live Mode, pipeline execution times depend on external provider latency (typically 15–30 seconds for full extraction across 5 stages).
- **Token Limits on Giant Repositories:** For codebases with millions of commits, naive ingestion exceeds LLM context windows without preliminary chunking and hierarchical summarization.

### Production Roadmap
Implement local model execution (e.g., via vLLM or Ollama with open-weight models like Llama 3 or Mistral) for entirely air-gapped on-premise installations.

---

## 5. Git Provider & Issue Tracker Integrations

### Current Architecture
- **GitHub:** Production integration via GitHub REST API with personal access tokens (`GITHUB_TOKEN`), supporting repositories, commits, PRs, and comments.
- **JSON Export Bundles:** Ingestion loaders for Slack channel JSON archives, Jira issue JSON exports, and Markdown documentation trees.

### Known Limitations
- **No Real-Time Webhook Listeners:** Ingestion currently operates via manual batch sync or upload. Continuous real-time synchronization via GitHub App webhooks or Slack event subscriptions is not yet enabled.
- **GitLab, Bitbucket & Linear:** Native API connectors for GitLab, Atlassian Bitbucket, Linear, and Notion are currently supported only via standard JSON/Markdown export formats.

### Production Roadmap
Add direct OAuth2 webhook receivers for GitLab, Bitbucket, and Linear following the extensible `Loader` protocol.

---

## 6. Graph Scale & Deep Traversal

### Current Architecture
RelayOps constructs bi-temporal graph nodes and edges stored in relational SQLite tables, queried via SQLite recursive Common Table Expressions (CTEs) up to 10 hops deep.

### Known Limitations
- **Complex Graph Algorithms:** While recursive CTEs excel at module dependency tracing, ownership calculation, and path finding, computationally intensive graph algorithms (e.g., PageRank across millions of nodes or community clustering) are less performant than dedicated graph database engines like Neo4j or Memgraph.
