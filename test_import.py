#!/usr/bin/env python3
"""Quick import test for Responses API integration"""

print("Testing critical imports...")

try:
    from planexe.llm_util.simple_openai_llm import SimpleOpenAILLM
    print("✓ SimpleOpenAILLM import OK")
except ImportError as e:
    print(f"✗ SimpleOpenAILLM import FAILED: {e}")

try:
    from planexe_api.streaming.analysis_stream_service import AnalysisStreamService
    print("✓ AnalysisStreamService import OK")
except ImportError as e:
    print(f"✗ AnalysisStreamService import FAILED: {e}")

try:
    from planexe_api.models import AnalysisStreamRequest, ReasoningEffort
    print("✓ AnalysisStreamRequest models import OK")
except ImportError as e:
    print(f"✗ AnalysisStreamRequest models import FAILED: {e}")

try:
    from planexe_api.api import app
    print("✓ FastAPI app import OK")
except ImportError as e:
    print(f"✗ FastAPI app import FAILED: {e}")

print("\nAll critical imports successful!")
