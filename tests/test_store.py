"""Supabase config gate. No network, no secrets file."""

from __future__ import annotations

import unittest

from src.db import usable_supabase_config


class ConfigTests(unittest.TestCase):
    def test_blank_and_placeholder_stay_local(self) -> None:
        self.assertFalse(usable_supabase_config("", ""))
        self.assertFalse(usable_supabase_config(None, None))
        self.assertFalse(
            usable_supabase_config(
                "https://YOUR_PROJECT_REF.supabase.co",
                "YOUR_ANON_KEY_placeholder_value",
            )
        )

    def test_real_looking_pair_is_usable(self) -> None:
        self.assertTrue(
            usable_supabase_config(
                "https://abcd.supabase.co",
                "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.example",
            )
        )


if __name__ == "__main__":
    unittest.main()
