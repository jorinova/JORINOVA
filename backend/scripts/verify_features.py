import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ai_services import voice_assistant, safety_guard, rules_engine, rejection_rules
from ai_services.schemas import TaskType

async def test_features():
    print("=== ALIS-X AI Features & Safety Verification ===")

    # 1. Voice Assistant Command Logic
    print("\n1. Testing Voice Assistant (NLU Parsing)...")
    commands = [
        "Go to hematology",
        "How do I process a malarial smear?",
        "Ouvrir le module de biochimie"
    ]
    for cmd in commands:
        result = voice_assistant.parse_command(cmd, lang='en')
        print(f"Input: {cmd}")
        # Look for intent/action in the result
        print(f"Result: {result}")

    # 2. Safety Guard Levels
    print("\n2. Testing Safety Guard (Danger Levels)...")
    safety_tests = [
        ("Open patient hub", "scientist"),
        ("Delete result for patient 123", "lab_technician"),
        ("Delete all patient records", "intern"),
        ("Drop table users", "super_admin")
    ]
    for cmd, role in safety_tests:
        assessment = safety_guard.assess_command(cmd, user_id=1, user_role=role)
        print(f"Input: [{role}] {cmd}")
        print(f"Level: {assessment.level} | Allowed: {assessment.action_allowed} | HoD Required: {assessment.requires_hod}")

    # 3. Clinical Rules
    print("\n3. Testing Clinical Rules (Interpretation)...")
    lab_results = [
        ('HGB', 6.5, 'LL'),   # Critical low
        ('GLUCOSE', 25.0, 'HH'), # Critical high
        ('WBC', 12.0, 'H')     # High
    ]
    for code, val, flag in lab_results:
        try:
            check = rules_engine.check_result(code, val, flag=flag)
            print(f"Result: {code}={val} [{flag}]")
            print(f"Significance: {check.significance} | Critical: {check.is_critical}")
            if check.panic_alerts:
                print(f"Alert: {check.panic_alerts[0].message}")
        except Exception as e:
            print(f"Error checking {code}: {e}")

    # 4. Rejection Rules
    print("\n4. Testing Rejection Rules...")
    rejection_tests = ["HGB", "PT", "GLUCOSE"]
    for code in rejection_tests:
        rules = rejection_rules.suggest_for_test(code)
        print(f"Test: {code} | Applicable Rejection Rules: {len(rules)}")
        if rules:
            print(f"  Example: {rules[0]['name']} ({rules[0]['severity']})")

    print("\nFeature Verification Complete.")

if __name__ == "__main__":
    asyncio.run(test_features())
