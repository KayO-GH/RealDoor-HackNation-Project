import tempfile
import unittest
from pathlib import Path

from realdoor.production import RealDoorV1, Settings


class ProductionServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.service = RealDoorV1(Settings(database_url=f"sqlite:///{root / 'db.sqlite'}", vault_path=root / "vault"))
        self.owner_token = self.service.issue_magic_link("owner@example.com")
        self.owner = self.service.verify_magic_link(self.owner_token)
        self.household = self.service.household(self.owner["account_id"], "Example household", True)

    def tearDown(self):
        self.temp.cleanup()

    def test_upload_requires_supported_small_non_duplicate_file(self):
        upload = self.service.upload(self.owner["account_id"], self.household["id"], "paystub.png", "image/png", "pay_stub", b"not a real png but safely isolated")
        self.assertEqual(upload["status"], "ready_for_review")
        with self.assertRaisesRegex(ValueError, "already uploaded"):
            self.service.upload(self.owner["account_id"], self.household["id"], "copy.png", "image/png", "pay_stub", b"not a real png but safely isolated")
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            self.service.upload(self.owner["account_id"], self.household["id"], "notes.txt", "text/plain", "pay_stub", b"text")

    def test_packet_requires_confirmed_evidence_and_share_is_code_protected(self):
        packet = self.service.packet(self.owner["account_id"], self.household["id"])
        self.assertEqual(packet["readiness_status"], "NEEDS_REVIEW")
        self.assertIn("NO_CONFIRMED_EVIDENCE", packet["review_reasons"])
        share = self.service.share(self.owner["account_id"], self.household["id"], packet["id"])
        token = share["share_url"].rsplit("/", 1)[-1]
        with self.assertRaises(PermissionError):
            self.service.public_packet(token, "00000000")
        self.assertEqual(self.service.public_packet(token, share["access_code"])["household"], "Example household")

    def test_other_account_cannot_access_household_and_deletion_removes_access(self):
        other = self.service.verify_magic_link(self.service.issue_magic_link("other@example.com"))
        with self.assertRaises(PermissionError):
            self.service.owned_household(other["account_id"], self.household["id"])
        self.service.delete_account(self.owner["account_id"])
        with self.assertRaises(PermissionError):
            self.service.account(self.owner["access_token"])


if __name__ == "__main__":
    unittest.main()
