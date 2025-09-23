# LLM Simplification Plan - September 22, 2025

**Author:** Claude Code using Sonnet 4
**Date:** 2025-09-22
**PURPOSE:** Replace the broken complex LLM system with simple OpenAI client approach

## 🚨 **Current Problem**

The Luigi pipeline is failing with:
```
ValueError('Invalid LLM class name in config.json: GoogleGenAI')
```

Root cause: The current system uses complex llama-index imports and dynamic class loading that's fragile and broken.

## 🎯 **Solution: Three-Model OpenAI Client System**

Replace the entire complex LLM system with a simple OpenAI client that supports:

1. **gpt-5-mini-2025-08-07** (Primary - OpenAI Direct)
2. **google/gemini-2.0-flash-001** (Fallback 1 - OpenRouter)
3. **google/gemini-2.5-flash** (Fallback 2 - OpenRouter)

## 📋 **Implementation Task List**

### **Phase 1: Create New Simple LLM System**

#### **Task 1.1: Update llm_config.json**
Replace entire file with simplified 3-model configuration:
```json
{
    "gpt-5-mini-2025-08-07": {
        "comment": "Latest GPT-5 Mini model - primary choice",
        "priority": 1,
        "provider": "openai",
        "model": "gpt-5-mini-2025-08-07"
    },
    "google/gemini-2.0-flash-001": {
        "comment": "Gemini 2.0 Flash via OpenRouter - fallback 1",
        "priority": 2,
        "provider": "openrouter",
        "model": "google/gemini-2.0-flash-001"
    },
    "google/gemini-2.5-flash": {
        "comment": "Gemini 2.5 Flash via OpenRouter - fallback 2",
        "priority": 3,
        "provider": "openrouter",
        "model": "google/gemini-2.5-flash"
    }
}
```

#### **Task 1.2: Create Simple LLM Wrapper**
Create: `planexe/llm_util/simple_openai_llm.py`

This wrapper must:
- Use OpenAI client for both direct and OpenRouter calls
- Handle GPT-5 reasoning API vs standard chat completions
- Maintain compatibility with existing LlamaIndex LLM interface
- Support the three target models

#### **Task 1.3: Update llm_factory.py**
- Remove all complex llama-index imports
- Replace dynamic `globals()[class_name]` loading
- Implement simple factory pattern for 2 providers
- Maintain existing function signatures for pipeline compatibility

### **Phase 2: Update Configuration Loading**

#### **Task 2.1: Update planexe/utils/planexe_llmconfig.py**
- Ensure it loads the new simplified JSON structure
- Remove any llama-index specific configuration handling

#### **Task 2.2: Verify Environment Variables**
Confirm these exist in `.env`:
- `OPENAI_API_KEY`
- `OPENROUTER_API_KEY`

### **Phase 3: Frontend Integration**

#### **Task 3.1: Update FastAPI Model Lists**
- Update `planexe_api/api.py` LLM model endpoint
- Ensure frontend dropdown shows 3 new models

#### **Task 3.2: Update Frontend Model Types**
- Update TypeScript types for the 3 new model names
- Test model selection in frontend

### **Phase 4: Testing & Validation**

#### **Task 4.1: Basic LLM Creation Test**
```python
# Test all three models can be created
llm1 = get_llm("gpt-5-mini-2025-08-07")
llm2 = get_llm("google/gemini-2.0-flash-001")
llm3 = get_llm("google/gemini-2.5-flash")
```

#### **Task 4.2: Pipeline Integration Test**
- Run minimal pipeline with `fast_but_skip_details`
- Verify Luigi tasks can create and use LLMs
- Test fallback behavior

#### **Task 4.3: End-to-End Test**
- Create plan via frontend
- Monitor Luigi pipeline execution
- Verify plan completes successfully

## 🔧 **Technical Implementation Details**

### **Simple OpenAI Wrapper Structure**
```python
from openai import OpenAI
import os

class SimpleOpenAILLM:
    def __init__(self, model: str, provider: str):
        if provider == "openai":
            self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        elif provider == "openrouter":
            self.client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=os.getenv("OPENROUTER_API_KEY")
            )
        self.model = model
        self.provider = provider

    def complete(self, prompt: str) -> str:
        if "gpt-5" in self.model:
            # Use GPT-5 reasoning API
            result = self.client.responses.create(
                model=self.model,
                input=prompt,
                reasoning={"effort": "low"},
                text={"verbosity": "low"}
            )
            return result.output_text
        else:
            # Use standard chat completions for Gemini
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                extra_headers={
                    "HTTP-Referer": "https://github.com/neoneye/PlanExe",
                    "X-Title": "PlanExe"
                } if self.provider == "openrouter" else {}
            )
            return completion.choices[0].message.content
```

### **Updated llm_factory.py Structure**
```python
from planexe.llm_util.simple_openai_llm import SimpleOpenAILLM
from planexe.utils.planexe_llmconfig import PlanExeLLMConfig

def get_llm(llm_name: str) -> SimpleOpenAILLM:
    config = planexe_llmconfig.llm_config_dict[llm_name]
    return SimpleOpenAILLM(
        model=config["model"],
        provider=config["provider"]
    )
```

## 🔄 **Backward Compatibility Strategy**

- Keep `get_llm()` function signature identical
- Maintain LlamaIndex LLM interface methods (`complete()`, etc.)
- Preserve existing error patterns expected by Luigi pipeline
- No changes needed to Luigi task code

## 📊 **Success Criteria**

- ✅ Luigi pipeline runs without "Invalid LLM class name" errors
- ✅ All three models can be instantiated successfully
- ✅ GPT-5 reasoning API works correctly
- ✅ OpenRouter Gemini models work correctly
- ✅ Frontend model selection works
- ✅ End-to-end plan generation completes

## 🗂️ **Files to Modify**

1. `llm_config.json` - Replace entire contents
2. `planexe/llm_util/simple_openai_llm.py` - Create new file
3. `planexe/llm_factory.py` - Simplify dramatically
4. `planexe_api/api.py` - Update model lists if needed
5. Frontend types - Update model names

## ⚠️ **Backup Strategy**

Before starting:
- Backup current `llm_config.json`
- Backup current `planexe/llm_factory.py`
- Test with shortest possible prompt first

## 🚀 **Next Steps for Developer**

1. **Create backup files**
2. **Implement Task 1.1** - Update llm_config.json
3. **Implement Task 1.2** - Create simple_openai_llm.py
4. **Implement Task 1.3** - Update llm_factory.py
5. **Test basic LLM creation** before proceeding
6. **Run minimal pipeline test**
7. **Full integration testing**

---

**Expected Time:** 4-6 hours implementation + testing
**Risk Level:** Low (simple replacement, clear rollback path)
**Dependencies:** OpenAI Python library, existing .env configuration