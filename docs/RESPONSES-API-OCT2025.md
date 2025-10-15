### OpenAI Responses API: Guide to Streamed Reasoning (Updated October 2025)
Guide to the OpenAI Responses API

This API is required for stateful conversations and models with internal reasoning (like GPT-5). It replaces the old ChatCompletions API.

Key Rules for Success:

Use input, Not messages: Your request body must use the input key, which takes an array of role/content objects. Sending the old messages key will fail.
Request Reasoning: For models that think step-by-step, you must include the reasoning parameter (e.g., reasoning: { "summary": "auto" }). If you don't, you won't get the model's thought process.
Parse the output Array: The response is not a single text field. It's an output array containing different blocks like message and reasoning. Your code must loop through this array to find the final text (content with type: "output_text") and the reasoning logs.
Set max_output_tokens Generously: Reasoning consumes output tokens. If the limit is too low, the model will complete its reasoning but have no tokens left to generate the final answer, resulting in an empty reply.
Use IDs for Conversation History: To continue a conversation, save the response.id from the previous turn and pass it as previous_response_id in your next request. This is how the API maintains state.


This guide is based on the latest OpenAI documentation as of October 2025, including the API reference at platform.openai.com/docs/api-reference/responses-streaming and the streaming responses guide at platform.openai.com/docs/guides/streaming-responses?api-mode=responses. The Responses API supports advanced features like ongoing conversation chains (stateful interactions), tool integration, and detailed reasoning using models from the GPT-5 series (such as gpt-5-nano-2025-08-07), o3, o3-mini, or o1 variants. It is the recommended replacement for the soon-to-be-deprecated Chat Completions API, especially for handling structured reasoning outputs.

Reasoning in the Responses API is key for "reasoning models" like o3 or o4-mini, where the AI does internal step-by-step thinking (chain-of-thought). You can stream this reasoning in real time, but it needs the right setup: specific parameters in your request, careful parsing of response events, and management of token usage (how the AI allocates processing power). These requirements match some common issues from your list, such as #2 (missing reasoning parameters), #4 (not checking the full output structure), and #8 (handling different stream event types). Below, I explain exactly what you need for successful streamed reasoning and what might be missing in your current setup, with references to your points.

#### Main Differences from the Chat Completions API
- **Endpoint and Request Format**: Send requests to POST /v1/responses. Use an "input" array instead of "messages." Each item in the "input" array includes a "role" (like "user," "assistant," or "system") and "content" (a simple string or an array of content types, such as text or images). This structure allows for more flexible, ongoing interactions compared to the older API.
- **Why It Matters**: The Chat Completions API (/v1/chat/completions) is being phased out by early 2026, and sticking with it will break new features like persistent reasoning. Switch to Responses for better support in tools from OpenAI and xAI (like Grok). Older software kits (SDKs) might still default to the old format, so update to the latest version (v1.5 or higher) that includes methods like client.responses.create().

#### Setting Up Streamed Reasoning Correctly
To get reasoning output streamed (delivered in chunks for real-time display), include these key elements in your request. Without them, you might only see a final summary or nothing at all.

1. **Enable Streaming and Reasoning Parameters**:
   - Add "stream": true to your request body. This turns on Server-Sent Events (SSE), where the response comes as a series of updates rather than one big chunk (#8).
   - Include a "reasoning" object: Set "summary" to "auto" (for a short overview) or "detailed" (full steps), and "effort" to "high" (for deeper thinking, though it uses more resources) (#2). If omitted, reasoning stays hidden internally.

2. **Handle Token Limits**:
   - Set "max_output_tokens" high enough (start with 8192 or more, up to the model's limit like 128,000 for o3). This controls visible output, but reasoning can use 50-80% of total tokens internally, leaving little for the final answer if the limit is too low (#3). Check usage details in the response for the "reasoning_tokens" breakdown to monitor costs.

3. **Store and Chain Responses**:
   - Use "store": true to save the response on OpenAI's servers for follow-up queries. Always capture and save the response's "id" in your database, then pass it back as "previous_response_id" in the next "input" for chained conversations (#5).

4. **Parsing the Streamed Response**:
   - The stream delivers separate event types: "response.reasoning.delta" for thinking steps (chunks of internal logic), "response.output_text.delta" for the final answer, and completion events like "response.done" with full usage stats (#4, #8).
   - Do not look only for a single text field like in Chat Completions. Instead, scan the "output" array in the final response: Look for items with "type": "reasoning" (for thinking traces) and "type": "message" (for answers, where content includes "type": "output_text").
   - Log the entire raw JSON response to your database for debugging (#9). If reasoning appears empty, increase effort or tokens, and confirm your parser handles all event types without assuming a simple delta stream.

#### Common Setup Gaps and Fixes
- **Missing Input Structure (#1, #7)**: Ensure you're sending "input" directly, not "messages." Test with raw JSON to your endpoint before using SDKs.
- **No Visible Reasoning (#2, #4)**: Add the "reasoning" object and parse the full "output" array. If using encryption (via "include": ["reasoning.encrypted_content"]), decrypt later with the response ID—it's not for live streams.
- **Stream Failures (#8)**: Your WebSocket or event handler must separate reasoning from output chunks. Without "stream": true, everything batches at the end.
- **Encryption and Storage Notes**: Options like "store": true are for privacy in long chains but don't affect basic streaming. Avoid assuming human-readable reasoning without the right params—o3 models handle it internally by default.

#### Quick Testing Steps
1. Send a basic request to /v1/responses with the essentials above. Log the full stream and check for reasoning events.
2. If no chunks appear, verify "stream": true and high effort/tokens.
3. For chains, reuse the "id" and inspect "usage" for token splits.
4. Upgrade your SDK and test on a reasoning model like o3-mini to confirm.

This setup ensures reliable streamed reasoning without contradictions to OpenAI's docs—reasoning is optional but powerful when configured, and streaming is event-based for better control. For full details, review the reasoning guide at platform.openai.com/docs/guides/reasoning.