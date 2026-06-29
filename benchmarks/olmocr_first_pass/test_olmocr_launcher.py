import unittest

from olmocr_launcher import can_bypass_memory_check


GIB = 1024**3


class DualT4BypassTest(unittest.TestCase):
    def test_allows_fp8_with_two_t4_gpus_and_tensor_parallelism(self):
        self.assertTrue(
            can_bypass_memory_check(
                ["Tesla T4", "Tesla T4"],
                [14 * GIB, 14 * GIB],
                tensor_parallel_size=2,
                model="allenai/olmOCR-2-7B-1025-FP8",
            )
        )

    def test_rejects_single_t4(self):
        self.assertFalse(
            can_bypass_memory_check(
                ["Tesla T4"],
                [14 * GIB],
                tensor_parallel_size=1,
                model="allenai/olmOCR-2-7B-1025-FP8",
            )
        )

    def test_rejects_non_fp8_model(self):
        self.assertFalse(
            can_bypass_memory_check(
                ["Tesla T4", "Tesla T4"],
                [14 * GIB, 14 * GIB],
                tensor_parallel_size=2,
                model="allenai/olmOCR-2-7B-1025",
            )
        )

    def test_rejects_less_than_fourteen_gib_per_gpu(self):
        self.assertFalse(
            can_bypass_memory_check(
                ["Tesla T4", "Tesla T4"],
                [13 * GIB, 13 * GIB],
                tensor_parallel_size=2,
                model="allenai/olmOCR-2-7B-1025-FP8",
            )
        )


if __name__ == "__main__":
    unittest.main()
