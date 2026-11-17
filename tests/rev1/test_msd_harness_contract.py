import unittest
from pathlib import Path

from infrastructure.sdn.p4.tests.test_msd_enforcement import (
    _compiled_sid_limit,
    _validate_compiled_sid_limit,
)


class MsdHarnessContractTests(unittest.TestCase):
    def test_compiled_msd4_profile_reports_four_sids(self):
        profile = Path("infrastructure/sdn/p4/build/msd_4/srv6_msd_4.json")
        self.assertEqual(_compiled_sid_limit(profile), 4)
        self.assertEqual(_validate_compiled_sid_limit(profile, 4), 4)

    def test_harness_refuses_profile_and_argument_mismatch(self):
        profile = Path("infrastructure/sdn/p4/build/msd_4/srv6_msd_4.json")
        with self.assertRaisesRegex(ValueError, "does not match compiled sid_list size 4"):
            _validate_compiled_sid_limit(profile, 3)


if __name__ == "__main__":
    unittest.main()
