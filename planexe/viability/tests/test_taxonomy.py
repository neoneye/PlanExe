
import unittest
import importlib
from planexe.viability import taxonomy
from planexe.viability.model_domain import DomainEnum
from planexe.viability.model_status import StatusEnum

class TestTaxonomy(unittest.TestCase):
    def test_domain_order_matches_enum(self):
        self.assertEqual(
            taxonomy.DOMAIN_ORDER,
            DomainEnum.value_list(),
            "DOMAIN_ORDER must match DomainEnum.value_list() exactly (including order).",
        )

    def test_reason_code_factor_covers_only_known_codes(self):
        all_codes = {c for lst in taxonomy.REASON_CODES_BY_DOMAIN.values() for c in lst}
        for code in taxonomy.REASON_CODE_FACTOR.keys():
            self.assertIn(code, all_codes, f"REASON_CODE_FACTOR references unknown code '{code}'")
            
    def test_reason_codes_whitelist_covers_all_domains(self):
        self.assertEqual(
            set(taxonomy.REASON_CODES_BY_DOMAIN.keys()),
            set(DomainEnum.value_list()),
            "REASON_CODES_BY_DOMAIN must have a key for each DomainEnum value (no extras, no missing).",
        )
        for domain, codes in taxonomy.REASON_CODES_BY_DOMAIN.items():
            self.assertIsInstance(codes, list, f"{domain}: whitelist must be a list")
            self.assertGreaterEqual(len(codes), 1, f"{domain}: whitelist should not be empty")
            for code in codes:
                self.assertIsInstance(code, str, f"{domain}: reason codes must be strings")
                self.assertRegex(code, r"^[A-Z0-9_]+$", f"{domain}: invalid reason code '{code}' (expect UPPER_SNAKE)")

    def test_default_evidence_has_entries_per_domain(self):
        self.assertEqual(
            set(taxonomy.DEFAULT_EVIDENCE_BY_DOMAIN.keys()),
            set(DomainEnum.value_list()),
            "DEFAULT_EVIDENCE_BY_DOMAIN must have a key for each domain.",
        )
        for domain, items in taxonomy.DEFAULT_EVIDENCE_BY_DOMAIN.items():
            self.assertIsInstance(items, list, f"{domain}: default evidence must be a list")
            self.assertGreaterEqual(len(items), 1, f"{domain}: must provide at least one default evidence item")
            for it in items:
                self.assertIsInstance(it, str, f"{domain}: evidence items must be strings")
                self.assertGreater(len(it.strip()), 0, f"{domain}: evidence items must be non-empty strings")
                criteria = taxonomy.EVIDENCE_ACCEPTANCE_CRITERIA.get(it)
                if criteria is not None:
                    self.assertIsInstance(criteria, str, f"{domain}: acceptance criteria entries must be strings when provided")
                    self.assertGreater(len(criteria.strip()), 0, f"{domain}: acceptance criteria entries must be non-empty strings when provided")

    # ---- Cross-map consistency -------------------------------------------------
    def test_strength_reason_codes_subset_of_whitelist(self):
        strength = taxonomy.STRENGTH_REASON_CODES
        all_codes = {c for lst in taxonomy.REASON_CODES_BY_DOMAIN.values() for c in lst}
        for code in strength:
            self.assertIn(code, all_codes, f"Strength code '{code}' must appear in a domain whitelist")

    def test_templates_reference_known_reason_codes(self):
        all_codes = {c for lst in taxonomy.REASON_CODES_BY_DOMAIN.values() for c in lst}
        for code, templates in taxonomy.EVIDENCE_TEMPLATES.items():
            self.assertIn(code, all_codes, f"EVIDENCE_TEMPLATES references unknown code '{code}'")
            self.assertIsInstance(templates, list, f"{code}: templates must be a list")
            for t in templates:
                self.assertIsInstance(t, str, f"{code}: template entries must be strings")
                self.assertGreater(len(t.strip()), 0, f"{code}: template entries must be non-empty strings")

    def test_evidence_acceptance_criteria_are_all_strings(self):
        for item in taxonomy.EVIDENCE_ACCEPTANCE_CRITERIA.values():
            self.assertIsInstance(item, str, f"EVIDENCE_ACCEPTANCE_CRITERIA values must be strings")
            self.assertGreater(len(item.strip()), 0, f"EVIDENCE_ACCEPTANCE_CRITERIA values must be non-empty strings")

    def test_reason_code_factor_covers_only_known_codes(self):
        # All codes referenced in REASON_CODE_FACTOR must be whitelisted in some domain
        all_codes = {c for lst in taxonomy.REASON_CODES_BY_DOMAIN.values() for c in lst}
        for code in taxonomy.REASON_CODE_FACTOR.keys():
            self.assertIn(code, all_codes, f"REASON_CODE_FACTOR references unknown code '{code}'")

        # Factors must be drawn from LIKERT_FACTOR_KEYS
        for code, factors in taxonomy.REASON_CODE_FACTOR.items():
            self.assertTrue(factors, f"{code}: factor set should not be empty")
            for f in factors:
                self.assertIn(f, taxonomy.LIKERT_FACTOR_KEYS, f"{code}: invalid factor '{f}'")

    def test_build_reason_code_fallbacks(self):
        factor_set_fn = taxonomy.TX.reason_code_factor_set
        fallbacks = taxonomy.TX.reason_code_fallback()
        for domain in taxonomy.DOMAIN_ORDER:
            self.assertIn(domain, fallbacks, f"Missing domain in fallbacks: {domain}")
            for factor in taxonomy.LIKERT_FACTOR_KEYS:
                code = fallbacks[domain].get(factor)
                self.assertIsInstance(code, str, f"No fallback code for ({domain}, {factor})")
                self.assertIn(code, taxonomy.REASON_CODES_BY_DOMAIN[domain],
                              f"Fallback '{code}' for ({domain}, {factor}) is not whitelisted for domain {domain}")
                self.assertIn(factor, factor_set_fn(code),
                              f"Fallback '{code}' for ({domain}, {factor}) does not map to that factor")

    # ---- Scoring policy sanity -------------------------------------------------
    def test_default_likert_policy_is_well_formed(self):
        self.assertIsInstance(taxonomy.LIKERT_MIN, int)
        self.assertIsInstance(taxonomy.LIKERT_MAX, int)
        self.assertLess(taxonomy.LIKERT_MIN, taxonomy.LIKERT_MAX)

        statuses_in_enum = {s.value for s in StatusEnum}
        self.assertEqual(
            set(taxonomy.DEFAULT_LIKERT_BY_STATUS.keys()),
            statuses_in_enum,
            "DEFAULT_LIKERT_BY_STATUS must cover exactly the StatusEnum values.",
        )

        for status, mapping in taxonomy.DEFAULT_LIKERT_BY_STATUS.items():
            self.assertEqual(set(mapping.keys()), set(taxonomy.LIKERT_FACTOR_KEYS),
                             f"{status}: factor keys mismatch LIKERT_FACTOR_KEYS")
            for factor, val in mapping.items():
                if status == StatusEnum.GRAY.value:
                    self.assertIsNone(val, "GRAY should have None defaults for all factors")
                else:
                    self.assertIsInstance(val, int, f"{status}.{factor}: default must be int")
                    self.assertGreaterEqual(val, taxonomy.LIKERT_MIN, f"{status}.{factor}: below min")
                    self.assertLessEqual(val, taxonomy.LIKERT_MAX, f"{status}.{factor}: above max")

    def test_factor_order_index_is_permutation(self):
        """FACTOR_ORDER_INDEX must include all factor keys and be a proper permutation of [0..n-1]."""
        keys = tuple(taxonomy.LIKERT_FACTOR_KEYS)
        idx_map = taxonomy.FACTOR_ORDER_INDEX
        for k in keys:
            self.assertIn(k, idx_map, f"Missing index for factor '{k}'")
            self.assertIsInstance(idx_map[k], int, f"Index for factor '{k}' must be int")
        self.assertEqual(set(idx_map.values()), set(range(len(keys))), "Indices must be 0..n-1 without gaps")

    def test_translate_reason_code_to_human_readable_with_existing_code(self):
        """Test that translate_reason_code_to_human_readable returns the correct template for existing reason codes."""
        # Test with a reason code that exists in the taxonomy
        reason_code = "CHANGE_MGMT_GAPS"
        expected_template = "Change plan v1 (communications, training, adoption KPIs)"
        
        result = taxonomy.TX.translate_reason_code_to_human_readable(reason_code)
        self.assertEqual(result, expected_template)
        
        # Verify it's actually in the evidence templates
        self.assertIn(reason_code, taxonomy.EVIDENCE_TEMPLATES)
        self.assertEqual(taxonomy.EVIDENCE_TEMPLATES[reason_code][0], expected_template)

    def test_translate_reason_code_to_human_readable_with_missing_code(self):
        """Test that translate_reason_code_to_human_readable returns the original code for non-existent reason codes."""
        # Test with a reason code that doesn't exist in the taxonomy
        reason_code = "NON_EXISTENT_CODE"
        
        result = taxonomy.TX.translate_reason_code_to_human_readable(reason_code)
        self.assertEqual(result, reason_code)
        
        # Verify it's not in the evidence templates
        self.assertNotIn(reason_code, taxonomy.EVIDENCE_TEMPLATES)
