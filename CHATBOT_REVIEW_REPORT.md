# DSVV Grievance Management System Chatbot Review

**Review date:** 21 October 2026  
**Scope:** Static review of chatbot UI, backend routes and services, AI/NLP modules, authentication, tracking and complaint integration, configuration, documentation, and the already-present chatbot test output. No application code was changed and no tests or live provider calls were run.

## Executive summary

The chatbot is a hybrid support assistant, not a single trained AI model. Its complaint intake, status lookup, and FAQ paths are implemented in application code. A separately configured OpenAI Chat Completions call can generate answers for general FAQ questions, but the repository's local `backend/.env` has no OpenAI API key configured. In this workspace the provider call therefore cannot authenticate and the chatbot falls back to its hand-written FAQ. Production deployment secrets are external to this repository and were not verifiable in this review.

No custom model training, fine-tuning, embeddings, vector search, or retrieval augmented generation are present. The complaint classifier uses weighted keyword rules, priority uses urgency keywords, duplicate detection uses Jaccard overlap on stemmed words, and NLP uses deterministic text processing. The OpenAI model is an optional FAQ answerer; it does not create complaints or retrieve complaint records.

The product has a substantial guided complaint flow, server side validation, an authenticated and ownership-scoped chatbot status lookup, and browser-based voice input/output. The primary gaps are unmeasured answer accuracy, brittle language/intent detection, no curated retrievable knowledge base, provider unavailability in local config, a likely session-resume defect in the web widget, inconsistent guest-flow documentation, and limited operational protections/observability for a deployed multi-worker service.

## How the chatbot works

1. The shared web widget is mounted on public, authentication, and portal pages. It posts text to `POST /api/chatbot/message`.
2. The Flask route enforces JSON/message/session limits, applies the general chatbot rate limit, and accepts an optional JWT.
3. The chatbot service routes messages through a deterministic conversation state machine. It handles complaint entry, FAQ/status intent, and otherwise tries the configured OpenAI provider before falling back to local FAQ content.
4. The provider prompt contains fixed portal facts and department directory text. It includes limited recent chat history, with common secrets and identifiers redacted.
5. Complaint submission uses the normal complaint service, which applies validation, classification, priority, assignment, audit/notification paths and an idempotency key. Chatbot actions do not let the model claim a successful submission.
6. Chat sessions are kept in MongoDB with random IDs and a 30-minute TTL. Status retrieval uses the authenticated complaint service and is scoped to the signed-in user. The separate public tracker is available by reference through the portal.

## Model, training, and knowledge source

| Question | Finding |
|---|---|
| Model configured in code | `gpt-4o-mini` by default, via the official OpenAI Python SDK and Chat Completions API. `OPENAI_MODEL` and legacy `CHATBOT_AI_MODEL` can override it. |
| Is it connected to an API? | There is a real server-side API integration. It is conditional: a non-empty provider key is required. The local `backend/.env` has no `OPENAI_API_KEY` or legacy key configured, so this workspace's FAQ path falls back locally. No live provider request was attempted. Deployment-side configuration cannot be established from these files. |
| How much is it trained? | The OpenAI model is a pretrained third-party model; this project does not train or fine-tune it. The project's own complaint analysis systems are explicitly `modelTrained: false`. No project-specific training dataset or training pipeline was found. |
| Custom training? | None found. |
| Knowledge base? | There is a small code-embedded FAQ, a static system prompt with portal rules and department contacts, and rules/keywords in source. There is no independently managed knowledge base, document ingestion, retrieval/search index, or citations. The provider is instructed to use the embedded facts, but generated replies are not verified against a source at answer time. |
| Fallback behavior | A local FAQ fallback is used when no key is configured or the provider errors. Responses expose `source`/`sourceNotice` for the normal FAQ path. The local FAQ is keyword matching rather than open-ended language understanding. |

## Feature review

### Accuracy and usefulness

**What works:** deterministic actions are safer than asking a language model to mutate records. Department routing and urgency reasons are explainable, and complaint records remain authoritative. The FAQ prompt explicitly tells the provider not to invent policy, status, assignment, or deadlines.

**Limitations:** there are no measured chatbot accuracy, intent, language, refusal, hallucination, or task-completion metrics in the reviewed materials. The department confidence is a score derived from keyword totals and margins, not a calibrated probability. The classifier can misroute paraphrases, spelling variants, mixed-language text, ambiguous terms, or new categories. Priority rules can miss implicit emergencies and can overreact to words such as “fire” or “shock” without context. Duplicate matching compares a maximum of 300 recent complaints and uses lexical overlap, so semantic paraphrases and older complaints can be missed.

**Assessment:** functional for narrow, common portal questions and guided workflows; accuracy is unquantified and should not be represented as production-validated.

### Performance

**What works:** rule-based flows are local and inexpensive; inputs and model output are capped; provider retries are disabled. The provider timeout is configurable and bounded to at most 20 seconds (12 seconds by default).

**Limitations:** no latency/load measurements, provider success rate, token/cost telemetry, or user-visible degradation metrics were found. When enabled, a general FAQ turn can block on a remote call for the timeout window. The in-memory rate limiter is process-local and resets on restart; each worker can independently accept its quota. MongoDB writes/reads are part of turn processing, and complaint duplicate analysis scans up to 300 candidate records.

**Assessment:** likely responsive for rule-based turns, but model-backed latency and scaling behavior are not established.

### Security and privacy

**Positive controls:** API keys are read server-side; prompts and replies are rendered using `textContent`; request bodies are capped; JWT identity is taken from a verified token; complaint status is owner scoped; chatbot session IDs are random and sessions expire; guest/mobile/IP limits are present in code; provider exceptions do not return secrets; common passwords, OTPs, email addresses, phone numbers, references, and scholar IDs are redacted before provider transmission and history storage.

**Risks and gaps:** redaction is regex-based and cannot reliably detect every personal/sensitive detail in free text. Complaint descriptions may still be sent to a third-party model, and no consent, retention, or provider data-handling notice is apparent in the chat flow. Rate limits are not shared across workers/instances. Auth tokens are stored by the web app in `localStorage`, which increases impact if an XSS defect is ever introduced elsewhere. Operational monitoring for abuse, provider errors, latency, or data deletion is not evident. The default model response remains ungrounded at runtime beyond its prompt.

**Assessment:** good baseline separation of model text from actions and private record access; privacy and deployment-level abuse controls need more work before relying on the chatbot at scale.

### Hindi, English, and Hinglish

The UI advertises all three. The service identifies Hindi by Devanagari characters and Hinglish using a finite set of Romanized markers; short utterances inherit the last style. It contains local reply variants and asks the provider to preserve script/style.

The approach handles common phrases but is not language detection or multilingual understanding. Roman Hindi spellings vary widely, code-switching is common, and a message with no recognized Hinglish marker can be treated as English. The fallback FAQ and intent/state machine each have separate keyword/phrase lists, so a word recognized in one path may not be understood in another. Language quality has no evaluation set or human review results.

### Voice assistant

Voice is implemented in the browser using Web Speech API (`SpeechRecognition`/`webkitSpeechRecognition`) for speech input and `speechSynthesis` for spoken output. It does not use a dedicated speech-to-text or text-to-speech provider and is unavailable when the browser lacks the relevant API. Locale selection is only Hindi (`hi-IN`) or English (`en-IN`); Hinglish is sent through English locale. Browser speech availability, accuracy, permissions, and processing/privacy depend on browser/device services. A transcript is submitted automatically when recognition ends, so transcription errors can reach the chatbot without a confirm-before-send step. Text entry remains the fallback.

### Complaint registration

The guided flow collects a category, campus location or lab/system label, description, identity/contact details where needed, then provides review/edit/cancel and submits through the standard complaint service. Server-side validation and idempotency are strong design choices. The current flow asks users to log in/register before starting complaint filing; test code asserts the unauthenticated path returns `auth_required`.

The backend contains guest-specific submission limits and guest handling code, and `docs/chatbot.md` and `backend/README.md` describe guest filing, but the current complaint-start guard and checked-in tests require login. This is a material documentation/behavior mismatch and leaves guest behavior unclear. Chat filing also does not collect evidence attachments, even though the normal form supports them. Description length, title, and location are simplified into a generated title and fixed campus coordinates; the normal form may collect richer structured details.

### Login and authentication

The chat endpoint is public for FAQ turns and accepts an optional JWT. Complaint filing explicitly asks for login, and active sessions are associated with the signed-in user. The chatbot status handler refuses private lookup without a user and calls the existing authorization-scoped complaint service. This is a sound security boundary. The widget provides login/register links. A session created before login is resumed after login via the same session ID, but a user must stay in the same widget context.

The web auth client stores the session/JWT in `localStorage`. This is an application-wide security consideration, not evidence of a chatbot bypass. Expired/invalid optional JWTs are not necessarily presented as a clear auth error for FAQ-only calls; protected complaint operations still require a valid authenticated identity.

### Complaint tracking

The chatbot recognizes references/status intents and can show status, department, priority, and timeline only after authenticated ownership checks. It will not reveal a record to an unauthenticated visitor and directs users to sign in. Public reference tracking exists separately at `/track.html`; the chatbot does not use that endpoint to display public tracking results. This is conservative for privacy, but gives guests an indirect, less conversational path.

## Existing issues and missing features

| Priority | Finding | Impact |
|---|---|---|
| P1 | No provider key is configured in local `.env`; only the local FAQ will answer general questions in this workspace. Deployment key presence was not verifiable. | Users may see a rule-based fallback while the UI identifies itself as an AI assistant. |
| P1 | No accuracy/evaluation evidence exists for FAQ answers, intent detection, multilingual behavior, routing, or voice transcription. | Quality claims and confidence cannot be substantiated. |
| P1 | Guest complaint docs conflict with current code/tests, which require login to begin. | User expectations and support instructions can be wrong; guest quotas/paths may be dead or legacy behavior. |
| P1 | Chatbot widget clears stored session ID on mount and close; `readSessionId()` is defined but never called. | Reloading/reopening does not reliably resume the MongoDB conversation despite documentation claiming tab-scoped resume. |
| P1 | OpenAI redaction is heuristic and chat flow lacks a clear provider-processing notice/consent. | Sensitive information not covered by current regex may leave the application boundary. |
| P2 | Knowledge is embedded in code/prompt with no retrieval, versioning, source citations, or content owner workflow. | Policy updates can be stale; generated answers can still be incorrect. |
| P2 | Hindi/Hinglish support relies on finite phrase lists and a binary script/marker heuristic. | Many valid spellings, code-switching, and natural utterances can fall back or route incorrectly. |
| P2 | Voice support relies on browser-dependent Web Speech APIs; no transcript confirmation, explicit locale choice, or app-wide voice path. | Access and recognition quality vary by browser/device; transcription mistakes can trigger unintended intents. |
| P2 | In-memory rate limits are per worker/process and reset on restart. | Multi-worker or horizontally scaled deployments do not enforce stated aggregate quotas. |
| P2 | No chatbot-specific latency, fallback, provider availability, cost, abandonment, or task-success instrumentation was found. | Incidents and quality regressions are difficult to see and improve. |
| P2 | Complaint chat does not handle evidence attachments; category/location/identity flow differs from the full form. | Users may need to restart in the form for richer submissions. |
| P3 | Existing recorded chatbot test output shows two failures around phone-number display/masking assertions and one skip. Its timestamp/currentness is unknown; this review did not rerun tests. | The checked-in recorded result is not a clean verification signal. The intended masking behavior should be made explicit and the corresponding assertions maintained. |
| P3 | Fixed FAQ, classifier keywords, command labels, urgent-word lists, language markers, and provider facts are duplicated across code/docs. | Updates can drift and create inconsistent answers. |

## Recommendations and priorities

### P0 — Establish what is live and protect users

1. Confirm OpenAI key/model/base URL in the actual deployment secret settings, without exposing the key; verify one harmless FAQ request and confirm the response source is `ai` or the explicitly labelled local fallback. Do not infer deployment state from a local `.env`.
2. Add a brief, clear notice before first model-backed use explaining that general chat text may be sent to the configured AI provider; advise users to keep complaint IDs and personal details out of free-text questions. Review redaction with realistic identifiers and multilingual examples.
3. Resolve the guest-filing contract: either document and implement guest filing consistently, or revise user-facing and developer documentation to state that login is required. Reassess whether guest-specific limits and guest identity paths remain needed.
4. Fix conversation resume behavior by deciding whether a chat session survives reload/reopen and making client storage match that policy. The current widget writes the ID but does not restore it and clears it on mount.

### P1 — Measure and improve answer quality

1. Create a versioned evaluation set covering common FAQ tasks, complaint intent, category/department routing, priority safety cases, auth/status boundary cases, Devanagari Hindi, Roman Hindi/Hinglish, spelling variants, code switching, and adversarial/prompt-injection inputs.
2. Score task completion, factual correctness, unsupported claims, language match, false urgency, missed urgent reports, and handoff quality. Set acceptance thresholds and maintain a regression set before changing prompts/rules/models.
3. Replace keyword-derived “confidence” labels with calibrated confidence or call them match strength. Add an explicit human review path for low-confidence or safety-sensitive classifications.
4. Give FAQ content a single maintained source with owners and update dates. Use retrieval over approved portal policy/help content with citations or links; keep complaint records and private status out of model retrieval and continue handling those through authorized backend functions.
5. Expand multilingual coverage from real campus phrasing and moderated user feedback. Keep all language variants in the same test cases and ensure English, Hindi, and Hinglish receive equivalent guidance.

### P1 — Improve reliability and speed

1. Capture server-side request latency and source (`ai`, local FAQ, guided flow, verified record), provider timeout/error counts, token usage/cost, and completion/abandonment events. Avoid logging raw user text or identifiers.
2. Use bounded provider concurrency and a clear timeout/fallback UX; consider caching only stable, non-personal FAQ answers. Keep provider fallback visible and consistent on every response path.
3. Move rate-limit counters to a shared store for multi-worker production and confirm proxy/IP handling matches each deployment host.
4. Benchmark the remote provider and MongoDB complaint paths with realistic concurrent traffic before advertising performance. Track p50/p95/p99 response times rather than relying on code defaults.

### P2 — Make voice and complaint intake easier to use

1. Add an explicit speech language selector (Hindi/English) and a transcript review/edit confirmation before sending. Clearly explain browser/device speech processing and offer a reliable text fallback.
2. Improve accessibility for keyboard use, screen readers, focus management, microphone state, and reduced-motion settings; verify on mobile browsers.
3. Add an attachment handoff to the existing evidence upload form or support the existing upload service in chat without duplicating validation/storage logic.
4. Offer contextual links/buttons for public tracking, sign-in, password help, and opening the full form. Preserve conversation state safely across auth navigation if that is an intended journey.

### P2 — Tighten privacy/security operations

1. Minimize provider-bound text and expand PII detection with tests for nonstandard phone formats, names, addresses, IDs, and Hindi/Romanized variants. Prefer collecting structured fields through the server flow rather than sending them through free-form FAQ chat.
2. Review localStorage token exposure and browser security controls (strict output escaping, CSP, dependency hygiene, HTTPS, short token lifetime/refresh behavior) across the whole app.
3. Define retention/deletion for MongoDB chatbot sessions and provider data, and add operational alerts for abuse, auth failures, provider errors, and elevated fallback rates.

## Verification evidence and limits

- Reviewed source: `frontend/assets/js/components/chatbot.js`, chatbot/auth frontend services, `backend/routes/chatbot_routes.py`, `backend/services/chatbot_service.py`, `backend/services/ai_service.py`, `backend/ai/classifier.py`, `backend/ai/priority.py`, `backend/ai/duplicate_detection.py`, `backend/utils/jwt_utils.py`, `backend/utils/rate_limit.py`, complaint service/routes, configuration, README/docs, and chatbot tests.
- Current local configuration check: `backend/.env` exists, but neither `OPENAI_API_KEY` nor legacy `CHATBOT_AI_API_KEY` is set; configured model falls back to `gpt-4o-mini` and the default OpenAI base URL.
- The repository includes `chatbot_test_result.txt` with 2 failures, 1 skipped, and other passing tests. It is a pre-existing output with no reliable timestamp in this review; no test suite was run as part of this task.
- Static review cannot establish deployment secret values, live provider reachability/quota, current production behavior, real-user accuracy, browser-specific voice support, or performance under load. Those require deployment/runtime verification and an evaluation run.

## Key source locations

- Chat widget and browser speech: `frontend/assets/js/components/chatbot.js`
- Chat endpoint: `backend/routes/chatbot_routes.py`
- FAQ/provider/fallback, state machine, session and tracking logic: `backend/services/chatbot_service.py`
- Model/API configuration: `backend/config.py`
- AI status and trained-model declaration: `backend/routes/ai_routes.py`
- Rule-based analysis: `backend/services/ai_service.py`, `backend/ai/classifier.py`, `backend/ai/priority.py`, `backend/ai/duplicate_detection.py`
- Identity/session checks: `backend/utils/jwt_utils.py`, `backend/database.py`
- Rate limiting: `backend/utils/rate_limit.py`
- Contradictory guest-flow documentation: `docs/chatbot.md` and `backend/README.md`
- Existing chatbot assertions and recorded test output: `backend/tests/test_chatbot.py`, `chatbot_test_result.txt`

- At review time, Git already reported local modifications in ackend/services/chatbot_service.py, ackend/services/complaint_service.py, ackend/tests/test_chatbot.py, and rontend/assets/js/components/chatbot.js. These were not edited during this review; the report is the only file created by this task. Findings describe the current working-tree contents, and the recorded test output may predate them.
