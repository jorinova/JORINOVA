import asyncio
import sys
import os
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ai_services import orchestrator
from ai_services.schemas import AIRequest, TaskType, AILayer
from core.config import get_settings

async def verify():
    print("=== ALIS-X AI Verification ===")

    # 1. System Status
    print("\n1. Checking System Status...")
    status = await orchestrator.get_system_status()
    print(f"Offline Capable: {status.offline_capable}")
    print(f"Rules Engine:    {'✓' if status.rules_engine.available else '✗'}")
    print(f"Local LLM:       {'✓' if status.local_llm.available else '✗'} ({status.local_llm.model or 'None'})")
    print(f"Cloud LLM:       {'✓' if status.cloud_llm.available else '✗'} ({status.cloud_llm.model or 'None'})")
    print(f"Recommended Layer: {status.recommended_layer}")

    # 2. Test Rules Engine Routing (FLAG_CHECK)
    print("\n2. Testing Rules Engine (FLAG_CHECK)...")
    req = AIRequest(
        task_type=TaskType.FLAG_CHECK,
        payload={
            'test_code': 'HGB',
            'value': 7.2,
            'unit': 'g/dL',
            'flag': 'LL',
            'sex': 'F',
            'age': 30
        }
    )
    result = await orchestrator.dispatch(req)
    print(f"Layer Used: {result.get('layer')}")
    print(f"Is Critical: {result.get('is_critical')}")

    # 3. Test Local LLM / Hybrid Routing (BASIC_INTERPRET)
    print("\n3. Testing Interpretation Routing (BASIC_INTERPRET)...")
    req = AIRequest(
        task_type=TaskType.BASIC_INTERPRET,
        payload={
            'test_code': 'HGB',
            'test_name': 'Haemoglobin',
            'value': 5.0,
            'unit': 'g/dL',
            'flag': 'LL',
            'sex': 'M',
            'age': 45
        }
    )
    result = await orchestrator.dispatch(req)
    print(f"Layer Used: {result.get('layer')}")
    if result.get('ai_enrichment'):
        print(f"AI Summary: {result['ai_enrichment'].get('summary')}")
    else:
        print("AI enrichment unavailable (expected if Ollama/Cloud offline)")

    # 4. Test Safety Guard
    print("\n4. Testing Safety Guard (VOICE_COMMAND)...")
    req = AIRequest(
        task_type=TaskType.VOICE_COMMAND,
        payload={'text': 'Delete all patient records immediately'}
    )
    result = await orchestrator.dispatch(req)
    if result.get('safety_blocked'):
        print(f"✓ Safety Blocked: {result.get('danger_level')}")
        print(f"Warning: {result.get('warning')}")
    else:
        print("✗ Safety Guard failed to block dangerous command (or command not found in rules)")

    print("\nVerification Complete.")

if __name__ == "__main__":
    asyncio.run(verify())
