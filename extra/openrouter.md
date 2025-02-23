# Using PlanExe with OpenRouter

[OpenRouter](https://openrouter.ai/) provides access to a large number of LLM models, that runs in the cloud.

Unfortunately there is no `free` model that works reliable with PlanExe.

In my experience, the `paid` models are the most reliable. Models like [google/gemini-2.0-flash-001](https://openrouter.ai/google/gemini-2.0-flash-001) and [openai/gpt-4o-mini](https://openrouter.ai/openai/gpt-4o-mini) are cheap and faster than running models on my own computer and without risk of it overheating.

I haven't been able to find a `free` model on OpenRouter that works well with PlanExe.

## Configuration

Visit [OpenRouter](https://openrouter.ai/), create an account, purchase 5 USD in credits (plenty for making a several plans), and generate an API key.

Copy `.env.example` to a new file called `.env`

Open the `.env` file in a text editor and insert your OpenRouter API key. Like this:

```
OPENROUTER_API_KEY='INSERT YOUR KEY HERE'
```

## Troubleshooting

Inside PlanExe, when clicking `Submit`, a new `Output Dir` should be created containing a `log.txt`. Open that file and scroll to the bottom, see if there are any error messages about what is wrong.

Report your issue on [Discord](https://neoneye.github.io/PlanExe-web/discord). Please include info about your system, such as: "I'm on macOS with M1 Max with 64 GB.".

## How to add a new OpenRouter model to `llm_config.json`

The [OpenRouter/rankings](https://openrouter.ai/rankings) page shows an overview of the most popular models. New models are added frequently

For a model to work with PlanExe, it must meet the following criteria:

- Minimum 8192 output tokens.
- Support structured output.
- Reliable. Avoid fragile setups where it works one day, but not the next day. If it's a beta version, be aware that it may stop working.
- Low latency.

Steps to add a model:

1. Copy the model id from the openrouter website.
2. Paste the model id into the `llm_config.json`.
3. Restart PlanExe to apply the changes.
