# OpenAI Responses API Conversation Attachment Notes

## Context
- Investigated how to continue a conversation when working with the OpenAI Responses API after hitting `'Conversations' object has no attribute 'responses'` in client code.
- Reviewed existing internal research docs summarizing the latest OpenAI documentation as of October 2025.

## Key Findings
1. **Use `client.responses.create` for follow-up turns.**
   - The Python and JavaScript SDKs expect you to call `responses.create` (or `responses.stream`) directly rather than looking for a nested `responses` namespace on `conversations`. The request body uses an `input` array of `{role, content}` items instead of the deprecated `messages` format.
2. **Attach responses with `conversation` or `previous_response_id`.**
   - To link a response to an existing conversation object, include the `conversation` field set to the `conversation_id` you created via the Conversations API. This persists state without manually replaying history.
   - Alternatively, capture every `response.id` and pass it back as `previous_response_id` on the next call. This automatically threads the next turn onto the prior response chain.
3. **Persist IDs and enable storage when you need long-lived context.**
   - Set `store: true` if you want OpenAI to retain responses beyond 30 days and ensure the conversation items avoid TTL expiry.
4. **Streaming requires the same identifiers.**
   - When streaming, keep using `response.id` from the final payload (not interim event IDs) as the value for `previous_response_id` on follow-ups.

## Action Items
- Update any code still calling `client.conversations.responses` to invoke `client.responses.create` with either a `conversation` ID or `previous_response_id`.
- Audit storage to make sure response IDs are persisted alongside conversation records.
