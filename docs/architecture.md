# System Architecture

The Gmail-to-WhatsApp-and-Telegram system continuously monitors Gmail mailboxes, extracts actionable deadlines, normalizes content, and dispatches real-time notifications and reminders.

```mermaid
flowchart TD
    subgraph Gmail [Google Workspace Gmail]
        G[Gmail API]
    end

    subgraph Connector [Gmail API Connector]
        O[OAuth 2.0 Client]
        H[History API / Incremental Sync]
        P[Pagination & Label Filters]
    end

    subgraph Normalization [Normalization & Deduplication]
        MIME[Recursive MIME Walker]
        SAN[HTML Sanitizer & Injection Guard]
        DEDUP[Unique Gmail ID & 24h Soft Dedup]
    end

    subgraph Pipeline [Processing Pipeline]
        CLS[11-Category Classifier]
        EXT[Deadline & Ambiguity Extractor]
    end

    subgraph Storage [Database - SQLite / PostgreSQL]
        DB_E[(Email Records)]
        DB_R[(Reminders)]
        DB_N[(Notification Deliveries)]
        DB_S[(Sync State)]
    end

    subgraph Scheduler [Background Worker / Dispatcher]
        POLL[Poll Worker]
        DISP[Reminder Dispatcher]
        DIG[Digest / Summary Generator]
    end

    subgraph Channels [Messaging Adapters]
        WA[WhatsApp Adapter]
        TG[Telegram Bot Adapter]
    end

    subgraph Recipients [Destination Targets]
        WAG[WhatsApp Group / 1:1]
        TGG[Telegram Group / Chat]
    end

    G -->|OAuth 2.0| O
    O --> H
    H --> P
    P --> MIME
    MIME --> SAN
    SAN --> DEDUP
    DEDUP --> CLS
    CLS --> EXT
    EXT --> Storage
    Storage <--> Scheduler
    Scheduler --> WA
    Scheduler --> TG
    WA --> WAG
    TG --> TGG
```

## Key Architectural Principles

1. **Category Inclusivity:**
   Processes all email categories (Academics, Examinations, Placements, Fees, Meetings, Personal, Bills, Travel, Newsletters, Security alerts, Other). An email is never dropped due to classification failure.

2. **Accurate Date Handling:**
   Distinguishes submission deadlines from general event dates, email timestamps, and ambiguous slash dates. Ambiguous dates are flagged for review rather than inventing false alarms.

3. **Channel Independence:**
   WhatsApp and Telegram adapters operate independently. A temporary rate limit or outage on one platform never blocks delivery on the other.

4. **Idempotency & Deduplication:**
   Every message dispatched is recorded in `NotificationDelivery` with an idempotency key (`{email_id}_{channel}_{destination_id}_{type}`) preventing duplicate sends even during retries or worker restarts.

5. **Security & Privacy:**
   - Tokens are encrypted at rest via symmetric Fernet encryption (`GOOGLE_TOKEN_ENCRYPTION_KEY`).
   - HTML bodies are sanitized, stripping `<script>`, `<iframe>`, and event handlers.
   - Credentials and bot tokens are automatically redacted in structured JSON logs.
   - Privacy mode allows sending notifications with subject, sender, and Gmail link only, without sharing email body contents into group chats.
