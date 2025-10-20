Conversation state
==================

Learn how to manage conversation state during a model interaction.

OpenAI provides a few ways to manage conversation state, which is important for preserving information across multiple messages or turns in a conversation.

Manually manage conversation state
----------------------------------

While each text generation request is independent and stateless, you can still implement **multi-turn conversations** by providing additional messages as parameters to your text generation request. Consider a knock-knock joke:

Manually construct a past conversation

```javascript
import OpenAI from "openai";

const openai = new OpenAI();

const response = await openai.responses.create({
    model: "gpt-5-mini-2025-08-07",
    input: [
        { role: "user", content: "knock knock." },
        { role: "assistant", content: "Who's there?" },
        { role: "user", content: "Orange." },
    ],
});

console.log(response.output_text);
```

```python
from openai import OpenAI

client = OpenAI()

response = client.responses.create(
    model="gpt-5-mini-2025-08-07",
    input=[
        {"role": "user", "content": "knock knock."},
        {"role": "assistant", "content": "Who's there?"},
        {"role": "user", "content": "Orange."},
    ],
)

print(response.output_text)
```

By using alternating `user` and `assistant` messages, you capture the previous state of a conversation in one request to the model.

To manually share context across generated responses, include the model's previous response output as input, and append that input to your next request.

In the following example, we ask the model to tell a joke, followed by a request for another joke. Appending previous responses to new requests in this way helps ensure conversations feel natural and retain the context of previous interactions.

Manually manage conversation state with the Responses API.

```javascript
import OpenAI from "openai";

const openai = new OpenAI();

let history = [
    {
        role: "user",
        content: "tell me a joke",
    },
];

const response = await openai.responses.create({
    model: "gpt-5-mini-2025-08-07",
    input: history,
    store: true,
});

console.log(response.output_text);

// Add the response to the history
history = [
    ...history,
    ...response.output.map((el) => {
        // TODO: Remove this step
        delete el.id;
        return el;
    }),
];

history.push({
    role: "user",
    content: "tell me another",
});

const secondResponse = await openai.responses.create({
    model: "gpt-5-mini-2025-08-07",
    input: history,
    store: true,
});

console.log(secondResponse.output_text);
```

```python
from openai import OpenAI

client = OpenAI()

history = [
    {
        "role": "user",
        "content": "tell me a joke"
    }
]

response = client.responses.create(
    model="gpt-5-mini-2025-08-07",
    input=history,
    store=False
)

print(response.output_text)

# Add the response to the conversation
history += [{"role": el.role, "content": el.content} for el in response.output]

history.append({ "role": "user", "content": "tell me another" })

second_response = client.responses.create(
    model="gpt-5-mini-2025-08-07",
    input=history,
    store=False
)

print(second_response.output_text)
```

OpenAI APIs for conversation state
----------------------------------

Our APIs make it easier to manage conversation state automatically, so you don't have to do pass inputs manually with each turn of a conversation.

### Using the Conversations API

The [Conversations API](/docs/api-reference/conversations/create) works with the [Responses API](/docs/api-reference/responses/create) to persist conversation state as a long-running object with its own durable identifier. After creating a conversation object, you can keep using it across sessions, devices, or jobs.

Conversations store items, which can be messages, tool calls, tool outputs, and other data.

Create a conversation

```python
conversation = openai.conversations.create()
```

In a multi-turn interaction, you can pass the `conversation` into subsequent responses to persist state and share context across subsequent responses, rather than having to chain multiple response items together.

Manage conversation state with Conversations and Responses APIs

```python
response = openai.responses.create(
  model="gpt-4.1",
  input=[{"role": "user", "content": "What are the 5 Ds of dodgeball?"}],
  conversation="conv_689667905b048191b4740501625afd940c7533ace33a2dab"
)
```

### Passing context from the previous response

Another way to manage conversation state is to share context across generated responses with the `previous_response_id` parameter. This parameter lets you chain responses and create a threaded conversation.

Chain responses across turns by passing the previous response ID

```javascript
import OpenAI from "openai";

const openai = new OpenAI();

const response = await openai.responses.create({
    model: "gpt-5-mini-2025-08-07",
    input: "tell me a joke",
    store: true,
});

console.log(response.output_text);

const secondResponse = await openai.responses.create({
    model: "gpt-5-mini-2025-08-07",
    previous_response_id: response.id,
    input: [{"role": "user", "content": "explain why this is funny."}],
    store: true,
});

console.log(secondResponse.output_text);
```

```python
from openai import OpenAI
client = OpenAI()

response = client.responses.create(
    model="gpt-5-mini-2025-08-07",
    input="tell me a joke",
)
print(response.output_text)

second_response = client.responses.create(
    model="gpt-5-mini-2025-08-07",
    previous_response_id=response.id,
    input=[{"role": "user", "content": "explain why this is funny."}],
)
print(second_response.output_text)
```

In the following example, we ask the model to tell a joke. Separately, we ask the model to explain why it's funny, and the model has all necessary context to deliver a good response.

Manually manage conversation state with the Responses API

```javascript
import OpenAI from "openai";

const openai = new OpenAI();

const response = await openai.responses.create({
    model: "gpt-5-mini-2025-08-07",
    input: "tell me a joke",
    store: true,
});

console.log(response.output_text);

const secondResponse = await openai.responses.create({
    model: "gpt-5-mini-2025-08-07",
    previous_response_id: response.id,
    input: [{"role": "user", "content": "explain why this is funny."}],
    store: true,
});

console.log(secondResponse.output_text);
```

```python
from openai import OpenAI
client = OpenAI()

response = client.responses.create(
    model="gpt-5-mini-2025-08-07",
    input="tell me a joke",
)
print(response.output_text)

second_response = client.responses.create(
    model="gpt-5-mini-2025-08-07",
    previous_response_id=response.id,
    input=[{"role": "user", "content": "explain why this is funny."}],
)
print(second_response.output_text)
```

Data retention for model responses

Response objects are saved for 30 days by default. They can be viewed in the dashboard [logs](/logs?api=responses) page or [retrieved](/docs/api-reference/responses/get) via the API. You can disable this behavior by setting `store` to `false` when creating a Response.

Conversation objects and items in them are not subject to the 30 day TTL. Any response attached to a conversation will have its items persisted with no 30 day TTL.

OpenAI does not use data sent via API to train our models without your explicit consent—[learn more](/docs/guides/your-data).

Even when using `previous_response_id`, all previous input tokens for responses in the chain are billed as input tokens in the API.

Managing the context window
---------------------------

Understanding context windows will help you successfully create threaded conversations and manage state across model interactions.

The **context window** is the maximum number of tokens that can be used in a single request. This max tokens number includes input, output, and reasoning tokens. To learn your model's context window, see [model details](/docs/models).

### Managing context for text generation

As your inputs become more complex, or you include more turns in a conversation, you'll need to consider both **output token** and **context window** limits. Model inputs and outputs are metered in [**tokens**](https://help.openai.com/en/articles/4936856-what-are-tokens-and-how-to-count-them), which are parsed from inputs to analyze their content and intent and assembled to render logical outputs. Models have limits on token usage during the lifecycle of a text generation request.

*   **Output tokens** are the tokens generated by a model in response to a prompt. Each model has different [limits for output tokens](/docs/models). For example, `gpt-4o-2024-08-06` can generate a maximum of 16,384 output tokens.
*   A **context window** describes the total tokens that can be used for both input and output tokens (and for some models, [reasoning tokens](/docs/guides/reasoning)). Compare the [context window limits](/docs/models) of our models. For example, `gpt-4o-2024-08-06` has a total context window of 128k tokens.

If you create a very large prompt—often by including extra context, data, or examples for the model—you run the risk of exceeding the allocated context window for a model, which might result in truncated outputs.

Use the [tokenizer tool](/tokenizer), built with the [tiktoken library](https://github.com/openai/tiktoken), to see how many tokens are in a particular string of text.

For example, when making an API request to the [Responses API](/docs/api-reference/responses) with a reasoning enabled model, like the [o1 model](/docs/guides/reasoning), the following token counts will apply toward the context window total:

*   Input tokens (inputs you include in the `input` array for the [Responses API](/docs/api-reference/responses))
*   Output tokens (tokens generated in response to your prompt)
*   Reasoning tokens (used by the model to plan a response)

Tokens generated in excess of the context window limit may be truncated in API responses.

![context window visualization](https://cdn.openai.com/API/docs/images/context-window.png)

You can estimate the number of tokens your messages will use with the [tokenizer tool](/tokenizer).

Next steps
----------

For more specific examples and use cases, visit the [OpenAI Cookbook](https://cookbook.openai.com), or learn more about using the APIs to extend model capabilities:

*   [Receive JSON responses with Structured Outputs](/docs/guides/structured-outputs)
*   [Extend the models with function calling](/docs/guides/function-calling)
*   [Enable streaming for real-time responses](/docs/guides/streaming-responses)
*   [Build a computer using agent](/docs/guides/tools-computer-use)
Streaming API responses
=======================

Learn how to stream model responses from the OpenAI API using server-sent events.

By default, when you make a request to the OpenAI API, we generate the model's entire output before sending it back in a single HTTP response. When generating long outputs, waiting for a response can take time. Streaming responses lets you start printing or processing the beginning of the model's output while it continues generating the full response.

Enable streaming
----------------

To start streaming responses, set `stream=True` in your request to the Responses endpoint:

```javascript
import { OpenAI } from "openai";
const client = new OpenAI();

const stream = await client.responses.create({
    model: "gpt-5",
    input: [
        {
            role: "user",
            content: "Say 'double bubble bath' ten times fast.",
        },
    ],
    stream: true,
});

for await (const event of stream) {
    console.log(event);
}
```

```python
from openai import OpenAI
client = OpenAI()

stream = client.responses.create(
    model="gpt-5",
    input=[
        {
            "role": "user",
            "content": "Say 'double bubble bath' ten times fast.",
        },
    ],
    stream=True,
)

for event in stream:
    print(event)
```

```csharp
using OpenAI.Responses;

string key = Environment.GetEnvironmentVariable("OPENAI_API_KEY")!;
OpenAIResponseClient client = new(model: "gpt-5", apiKey: key);

var responses = client.CreateResponseStreamingAsync([
    ResponseItem.CreateUserMessageItem([
        ResponseContentPart.CreateInputTextPart("Say 'double bubble bath' ten times fast."),
    ]),
]);

await foreach (var response in responses)
{
    if (response is StreamingResponseOutputTextDeltaUpdate delta)
    {
        Console.Write(delta.Delta);
    }
}
```

The Responses API uses semantic events for streaming. Each event is typed with a predefined schema, so you can listen for events you care about.

For a full list of event types, see the [API reference for streaming](/docs/api-reference/responses-streaming). Here are a few examples:

```python
type StreamingEvent =
	| ResponseCreatedEvent
	| ResponseInProgressEvent
	| ResponseFailedEvent
	| ResponseCompletedEvent
	| ResponseOutputItemAdded
	| ResponseOutputItemDone
	| ResponseContentPartAdded
	| ResponseContentPartDone
	| ResponseOutputTextDelta
	| ResponseOutputTextAnnotationAdded
	| ResponseTextDone
	| ResponseRefusalDelta
	| ResponseRefusalDone
	| ResponseFunctionCallArgumentsDelta
	| ResponseFunctionCallArgumentsDone
	| ResponseFileSearchCallInProgress
	| ResponseFileSearchCallSearching
	| ResponseFileSearchCallCompleted
	| ResponseCodeInterpreterInProgress
	| ResponseCodeInterpreterCallCodeDelta
	| ResponseCodeInterpreterCallCodeDone
	| ResponseCodeInterpreterCallInterpreting
	| ResponseCodeInterpreterCallCompleted
	| Error
```

Read the responses
------------------

If you're using our SDK, every event is a typed instance. You can also identity individual events using the `type` property of the event.

Some key lifecycle events are emitted only once, while others are emitted multiple times as the response is generated. Common events to listen for when streaming text are:

```text
- `response.created`
- `response.output_text.delta`
- `response.completed`
- `error`
```

For a full list of events you can listen for, see the [API reference for streaming](/docs/api-reference/responses-streaming).

Advanced use cases
------------------

For more advanced use cases, like streaming tool calls, check out the following dedicated guides:

*   [Streaming function calls](/docs/guides/function-calling#streaming)
*   [Streaming structured output](/docs/guides/structured-outputs#streaming)

Moderation risks are irrelevant to streaming responses and to our project!!!
---------------

Was this page useful?