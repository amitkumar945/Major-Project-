# Chatbot Remediation Report

**Date:** 21 October 2026  
**Related review:** [CHATBOT_REVIEW_REPORT.md](CHATBOT_REVIEW_REPORT.md)

## Result

Implemented targeted changes for API configuration handling, provider privacy communication, authenticated complaint data handling, chat session continuity, multilingual detection, voice input confirmation, and shared chatbot rate limiting. Existing complaint, login, tracking, FAQ, and voice capabilities remain available.

## Changes made

### API connectivity and reliability

- Kept the existing server-side OpenAI Chat Completions integration and its local FAQ fallback.
- Provider keys are now trimmed before use. An empty or whitespace-only key is treated as unconfigured and does not trigger an API call. Provider base URLs and model names also receive safe whitespace/default handling.
- Added regression coverage for whitespace-only keys and verified provider errors continue to return the local fallback without exposing provider details.
- Chat requests continue to use the server-side OpenAI Chat Completions client when configured; local FAQs remain the fallback.
- No API key was added or printed. The live integration test was explicitly attempted but skipped because `OPENAI_API_KEY` is not configured. The real provider connection therefore remains unverified.

### Security and authentication

- Added a visible notice that general chat questions may be sent to the configured provider and users should not include passwords, OTPs, complaint references, or personal details.
- Preserved the current login requirement for chatbot complaint filing and ownership checks for private status lookup.
- Restricted registered submitter email/mobile overrides at the shared complaint-service boundary. Standard complaint API calls now keep the authenticated account snapshot. The chatbot opts into an override only after its guided contact confirmation, preserving that existing chat feature.
- No sensitive user data or credentials were included in reports or test output.

### Chat session continuity

- The widget now restores its session ID from `sessionStorage` on startup instead of deleting it.
- Closing/minimizing the panel no longer discards the active session ID. FAQ turns also retain the ID, preserving server-side conversation history across follow-up questions.
- Session expiry and authorization remain enforced by the backend.

### Multilingual handling

- Expanded the shared Hinglish markers in the backend and web client, including common variants such as `mere`, `kaam`, `nahi`, `raha/rahi`, and `vibhag`.
- Added backend regression cases for Hinglish, Hindi, and English style detection and localized department/status/complaint FAQ routing.

### Voice experience

- Starting microphone capture now cancels active spoken playback to reduce audio feedback.
- Recognized speech is placed in the input field for review; the user presses Send to submit it. This avoids silently submitting a poor transcription.
- The browser's Web Speech APIs remain the speech engine, so recognition quality and availability still vary by browser, device, locale, and network.

### Shared chatbot rate limiting

- Chatbot quotas now use an atomic MongoDB fixed-window counter shared by application workers, with a TTL index to expire old windows.
- Client identifiers are SHA-256 hashed before storage. If MongoDB is temporarily unavailable, requests fall back to the in-process limiter so the endpoint remains available.
- Authentication and OTP buckets retain their existing process-local limiter.

## Latest verification (21 October 2026)

- Chatbot test module in the project virtual environment: **82 passed, 1 skipped**. The skipped case is the opt-in live OpenAI integration test.
- Live provider check: attempted with the integration flag enabled; skipped because no `OPENAI_API_KEY` is configured. No secret value was read into the report or output.
- Local HTTP smoke checks: verified Hindi FAQ routing, Hinglish FAQ routing, login gating, guided complaint flow transitions, and authenticated complaint tracking. Test records used an isolated database that was dropped after the checks.
- `node --check frontend/assets/js/components/chatbot.js`: passed.
- `git diff --check`: passed.
- Pytest emitted a non-fatal cache-path warning due to an existing cache directory. The initial system-Python test invocation also failed because that interpreter lacks the project's `openai` package; the project virtual environment run above completed successfully.
- Real browser UI/voice testing could not be performed: the provided CUA environment exposed no browser or app surface, and its browser launch attempt returned unavailable. No browser automation fallback was used.

## Still needs attention

1. Configure the provider API key securely in the actual deployment and verify a live, harmless FAQ request. This repository cannot supply the credential, and local config currently selects fallback behavior.
2. The chatbot quota is shared through MongoDB; consider monitoring the fallback-to-local path and applying the same shared limiter to authentication/OTP if deployment uses multiple workers.
3. Build an evaluated, versioned multilingual FAQ/intent test set and measure answer correctness, routing precision, urgency misses, latency, fallbacks, and task completion. No new model training or retrieval knowledge base was introduced.
4. Browser-test microphone permission, Hindi/English recognition, transcript review, spoken replies, keyboard use, and screen-reader behavior across supported devices once a browser test surface is available.
5. Review provider retention/processing policy and expand PII tests. The notice and existing redaction reduce risk but cannot detect every name, address, or sensitive detail in free text.
6. Resolve the guest-flow documentation mismatch noted in the review. Current backend behavior requires login to begin chatbot complaint filing, while older documentation describes guest filing.

## Working-tree note

`backend/services/chatbot_service.py`, `backend/services/complaint_service.py`, `backend/tests/test_chatbot.py`, and `frontend/assets/js/components/chatbot.js` were already locally modified before this remediation task. Those edits were preserved; the targeted changes above were applied on top. The review report is also present as an untracked file.
