# Using PlanExe with Mistral

This is for **advanced users** that already have PlanExe working.

If you are getting started with PlanExe, I (the developer of PlanExe) recommend following the [openrouter.md](openrouter.md) instructions. Stick with the default settings. 

If you want to use Mistral, then [OpenRouter has several mistral models](https://openrouter.ai/models?q=mistral). 

## Why use Mistral?

Mistral can have run your own fine tuned model in the cloud. If you have sensitive business data that you don't want to share with the world, then this is one way to do it.

Create an account on the [mistral.ai](https://mistral.ai/) website and buy 10 EUR of credits.

List of [available models](https://docs.mistral.ai/getting-started/models/models_overview/).

Using the free models, and the API is rate limited to 1 request per second. PlanExe cannot deal with rate limiting and PlanExe does 70-100 requests, so it's likely going to yield errors.

## Create API key

1. Visit [api-keys](https://console.mistral.ai/api-keys).
2. Click `Create new key` and name the new key `PlanExe`.
3. In the `.env` file in the root dir of the PlanExe repo, create a row named `MISTRAL_API_KEY`. Copy/paste the newly created api key into that row.

The `.env` file should look something like the following, with your own key inserted.
```
MISTRAL_API_KEY='AWkg3SxFTLWaPJClbASfv9h3VPItroof'
```

## Edit the `llm_config.json`

The JSON should look something like this:

```json
{
    "mistral-paid-large": {
        "comment": "This is paid. Possible free to use for a limited time. Check the pricing before use.",
        "class": "MistralAI",
        "arguments": {
            "model": "mistral-large-latest",
            "api_key": "${MISTRAL_API_KEY}",
            "temperature": 1.0,
            "timeout": 60.0,
            "max_tokens": 8192,
            "max_retries": 5
        }
    }
}
```

## Use the Mistral model

1. Restart PlanExe
2. Go to the `Settings` tab
3. Select the `mistral-paid-large` model.
