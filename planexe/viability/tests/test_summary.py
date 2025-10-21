from typing import Sequence
import unittest
from planexe.viability.summary import RecommendationEnum

class TestRecommendationEnum(unittest.TestCase):
    def uncovered(self, statuses: Sequence[str]) -> RecommendationEnum:
        return RecommendationEnum.determine(statuses=statuses, red_gray_covered=False)

    def covered(self, statuses: Sequence[str]) -> RecommendationEnum:
        return RecommendationEnum.determine(statuses=statuses, red_gray_covered=True)

    def test_uncovered__go(self):
        self.assertEqual(self.uncovered(["GREEN", "YELLOW"]), RecommendationEnum.GO)
        self.assertEqual(self.uncovered([]), RecommendationEnum.GO)
        # Unknown strings don't trigger RED/GRAY logic
        self.assertEqual(self.uncovered(["blue", "green"]), RecommendationEnum.GO)

    def test_uncovered__proceed_with_caution(self):
        self.assertEqual(self.uncovered(["GRAY", "GREEN"]), RecommendationEnum.PROCEED_WITH_CAUTION)
        self.assertEqual(self.uncovered(["GRAY"]), RecommendationEnum.PROCEED_WITH_CAUTION)

    def test_uncovered__hold(self):
        self.assertEqual(self.uncovered(["RED", "GREEN"]), RecommendationEnum.HOLD)
        self.assertEqual(self.uncovered(["rEd"]), RecommendationEnum.HOLD)

    def test_uncovered__never_yields_go_if_fp0(self):
        samples = [
            [], ["GREEN"], ["YELLOW"], ["GREEN", "YELLOW"],
            ["GRAY"], ["GRAY", "GREEN"], ["RED"], ["RED", "GRAY"], ["RED", "YELLOW"],
            ["blue"], ["blue", "GRAY"], ["blue", "RED"],
        ]
        for st in samples:
            rec = self.uncovered(st)
            self.assertNotEqual(
                rec, RecommendationEnum.GO_IF_FP0,
                f"Unexpected GO_IF_FP0 for statuses={st}",
            )

    def test_covered__go(self):
        # No RED/GRAY -> coverage flag irrelevant
        self.assertEqual(self.covered(["GREEN", "YELLOW"]), RecommendationEnum.GO)
        self.assertEqual(self.covered([]), RecommendationEnum.GO)

    def test_covered__go_if_fp0(self):
        self.assertEqual(self.covered(["GRAY"]), RecommendationEnum.GO_IF_FP0)
        self.assertEqual(self.covered(["RED", "GREEN"]), RecommendationEnum.GO_IF_FP0)
        self.assertEqual(self.covered(["RED", "GRAY", "YELLOW"]), RecommendationEnum.GO_IF_FP0)

    def test_covered__never_yields_hold_or_proceed_with_caution(self):
        samples = [
            [], ["GREEN"], ["YELLOW"], ["GREEN", "YELLOW"],
            ["GRAY"], ["GRAY", "GREEN"], ["RED"], ["RED", "GRAY"], ["RED", "YELLOW"],
            ["blue"], ["blue", "GRAY"], ["blue", "RED"],
        ]
        forbidden = {RecommendationEnum.HOLD, RecommendationEnum.PROCEED_WITH_CAUTION}
        for st in samples:
            rec = self.covered(st)
            self.assertNotIn(
                rec, forbidden,
                f"Unexpected {rec} for statuses={st}",
            )
    
    def test_flag_irrelevant_when_no_red_gray(self):
        s = ["GREEN", "YELLOW"]
        a = RecommendationEnum.determine(statuses=s, red_gray_covered=False)
        b = RecommendationEnum.determine(statuses=s, red_gray_covered=True)
        self.assertEqual(a, RecommendationEnum.GO)
        self.assertEqual(b, RecommendationEnum.GO)
        self.assertEqual(a, b)

    def test_order_invariance(self):
        s = ["RED", "GRAY", "YELLOW", "GREEN"]
        self.assertEqual(
            RecommendationEnum.determine(statuses=s, red_gray_covered=True),
            RecommendationEnum.determine(statuses=list(reversed(s)), red_gray_covered=True),
        )