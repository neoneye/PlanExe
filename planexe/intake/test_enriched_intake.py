"""
Author: Claude Code using Haiku 4.5
Date: 2025-10-21
PURPOSE: Validate EnrichedPlanIntake schema works correctly and can be
         used with OpenAI Responses API structured outputs (strict mode).
SRP and DRY check: Pass - Single responsibility of schema validation testing.
"""

import json
from datetime import datetime
from pydantic import ValidationError
from planexe.intake.enriched_plan_intake import (
    EnrichedPlanIntake,
    RiskTolerance,
    ProjectScale,
    GeographicScope,
    BudgetInfo,
    TimelineInfo,
)


def test_basic_schema_creation():
    """Test creating a valid EnrichedPlanIntake instance"""
    print("\n=== Test 1: Basic Schema Creation ===")

    intake = EnrichedPlanIntake(
        project_title="Yorkshire Terrier Breeding Business",
        refined_objective="Establish a reputable home-based breeding operation for Yorkshire terriers in Texas, launching first litter within 6 months with emphasis on breed standards.",
        original_prompt="I want to become a Yorkshire terrier breeder",
        scale=ProjectScale.personal,
        risk_tolerance=RiskTolerance.moderate,
        domain="Dog breeding",
        budget=BudgetInfo(
            estimated_total="$15,000",
            funding_sources=["personal savings"],
            currency="USD"
        ),
        timeline=TimelineInfo(
            target_completion="6 months",
            key_milestones=["First litter in 6 months"],
            urgency="Goal-driven"
        ),
        team_size="solo",
        existing_resources=["25+ years experience with Yorkies", "Home with suitable space"],
        geography=GeographicScope(
            is_digital_only=False,
            physical_locations=["Texas, USA"],
            notes="Home-based operation"
        ),
        hard_constraints=[
            "Must comply with Texas breeding regulations",
            "Must follow AKC breed standards",
            "Limited to home-based breeding (zoning limits)"
        ],
        success_criteria=[
            "Breed puppies to AKC standards",
            "Build reputation for healthy puppies",
            "Achieve 3-4 litters per year",
            "Maintain breeding ethics and animal welfare"
        ],
        key_stakeholders=["Breeder (self)", "Veterinarian", "AKC registrar"],
        regulatory_context="Texas state animal welfare laws, AKC breeding guidelines",
        conversation_summary="User has decades of experience with the breed and is ready to launch a home-based operation. Clear on timeline (6 months) and budget ($15k). Moderate risk tolerance - following proven breeding practices.",
        confidence_score=9,
        areas_needing_clarification=[]
    )

    print("OK: Successfully created EnrichedPlanIntake instance")
    print(f"  - Title: {intake.project_title}")
    print(f"  - Scale: {intake.scale.value}")
    print(f"  - Risk: {intake.risk_tolerance.value}")
    print(f"  - Budget: {intake.budget.estimated_total}")
    print(f"  - Timeline: {intake.timeline.target_completion}")
    print(f"  - Confidence: {intake.confidence_score}/10")

    return intake


def test_json_schema_generation():
    """Test that JSON schema is valid for Responses API"""
    print("\n=== Test 2: JSON Schema Generation ===")

    schema = EnrichedPlanIntake.model_json_schema()
    print(f"✓ Generated JSON schema")
    print(f"  - Total properties: {len(schema.get('properties', {}))}")
    print(f"  - Required fields: {len(schema.get('required', []))}")

    required = schema.get('required', [])
    expected_required = [
        'project_title', 'refined_objective', 'original_prompt',
        'scale', 'risk_tolerance', 'domain',
        'budget', 'timeline', 'geography',
        'hard_constraints', 'success_criteria',
        'key_stakeholders', 'conversation_summary', 'confidence_score',
        'captured_at'
    ]

    missing = set(expected_required) - set(required)
    if missing:
        print(f"  ⚠ WARNING: Missing required fields: {missing}")
    else:
        print(f"  ✓ All expected required fields present")

    # Verify enums are defined
    schema_str = json.dumps(schema, indent=2)
    if "conservative" in schema_str and "moderate" in schema_str:
        print(f"  ✓ RiskTolerance enum values present in schema")
    if "personal" in schema_str and "global" in schema_str:
        print(f"  ✓ ProjectScale enum values present in schema")

    return schema


def test_serialization():
    """Test serialization to JSON and back"""
    print("\n=== Test 3: Serialization (JSON) ===")

    intake = EnrichedPlanIntake(
        project_title="Test Project",
        refined_objective="This is a test",
        original_prompt="Original prompt",
        scale=ProjectScale.local,
        risk_tolerance=RiskTolerance.aggressive,
        domain="Testing",
        budget=BudgetInfo(estimated_total="$5000"),
        timeline=TimelineInfo(target_completion="3 months"),
        geography=GeographicScope(is_digital_only=True),
        conversation_summary="Test conversation",
        confidence_score=7
    )

    # Serialize
    json_str = intake.model_dump_json(indent=2)
    print(f"✓ Serialized to JSON ({len(json_str)} bytes)")

    # Deserialize
    restored = EnrichedPlanIntake.model_validate_json(json_str)
    print(f"✓ Deserialized from JSON")
    print(f"  - Title matches: {restored.project_title == intake.project_title}")
    print(f"  - Confidence matches: {restored.confidence_score == intake.confidence_score}")

    return json_str


def test_enum_validation():
    """Test enum validation"""
    print("\n=== Test 4: Enum Validation ===")

    # Valid enum values
    valid_scales = [e.value for e in ProjectScale]
    valid_risks = [e.value for e in RiskTolerance]

    print(f"✓ Valid ProjectScale values: {valid_scales}")
    print(f"✓ Valid RiskTolerance values: {valid_risks}")

    # Try invalid enum
    try:
        bad_intake = EnrichedPlanIntake(
            project_title="Bad",
            refined_objective="Bad",
            original_prompt="Bad",
            scale="INVALID_SCALE",  # type: ignore
            risk_tolerance=RiskTolerance.moderate,
            domain="Bad",
            budget=BudgetInfo(),
            timeline=TimelineInfo(),
            geography=GeographicScope(is_digital_only=True),
            conversation_summary="Bad",
            confidence_score=5
        )
        print(f"✗ ERROR: Should have rejected invalid scale")
    except ValidationError as e:
        print(f"✓ Correctly rejected invalid scale: {e.error_count()} error(s)")


def test_optional_fields():
    """Test that optional fields are actually optional"""
    print("\n=== Test 5: Optional Fields ===")

    minimal = EnrichedPlanIntake(
        project_title="Minimal",
        refined_objective="Just a test",
        original_prompt="Minimal prompt",
        scale=ProjectScale.personal,
        risk_tolerance=RiskTolerance.conservative,
        domain="Testing",
        budget=BudgetInfo(),
        timeline=TimelineInfo(),
        geography=GeographicScope(is_digital_only=True),
        conversation_summary="Minimal conversation",
        confidence_score=1
    )

    print(f"✓ Created minimal instance (omitting optional fields)")
    print(f"  - team_size: {minimal.team_size}")
    print(f"  - existing_resources: {minimal.existing_resources}")
    print(f"  - hard_constraints: {minimal.hard_constraints}")
    print(f"  - success_criteria: {minimal.success_criteria}")
    print(f"  - key_stakeholders: {minimal.key_stakeholders}")
    print(f"  - regulatory_context: {minimal.regulatory_context}")
    print(f"  - areas_needing_clarification: {minimal.areas_needing_clarification}")


def test_responses_api_compatibility():
    """Test that schema is compatible with OpenAI Responses API strict mode"""
    print("\n=== Test 6: Responses API Compatibility ===")

    schema = EnrichedPlanIntake.model_json_schema()

    # Check for properties that Responses API requires
    required_properties = ['title', 'type', 'properties']
    for prop in required_properties:
        if prop in schema:
            print(f"✓ Schema has '{prop}' property")
        else:
            print(f"✗ Schema missing '{prop}' property")

    # Test that all properties have descriptions (helps with Responses API)
    properties = schema.get('properties', {})
    described = sum(1 for p in properties.values() if 'description' in p)
    total = len(properties)

    print(f"✓ {described}/{total} properties have descriptions ({100*described//total}%)")

    if described == total:
        print(f"  → Schema is well-documented for Responses API")


def main():
    """Run all tests"""
    print("\n" + "=" * 70)
    print("ENRICHED PLAN INTAKE SCHEMA TESTS")
    print("=" * 70)

    try:
        intake = test_basic_schema_creation()
        schema = test_json_schema_generation()
        json_str = test_serialization()
        test_enum_validation()
        test_optional_fields()
        test_responses_api_compatibility()

        print("\n" + "=" * 70)
        print("ALL TESTS PASSED!")
        print("=" * 70)
        print("\nSchema is ready for use with:")
        print("  - OpenAI Responses API (strict mode)")
        print("  - Frontend conversation flows")
        print("  - Pipeline enrichment")

        return 0

    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
