#!/usr/bin/env python3
"""Run olmOCR with a narrow Kaggle dual-T4 preflight workaround."""

import logging
import os
import sys


GIB = 1024**3
OFFICIAL_MIN_BYTES = 15 * GIB
DUAL_T4_MIN_BYTES = 14 * GIB


def can_bypass_memory_check(gpu_names, gpu_memories, tensor_parallel_size, model):
    """Return True only for the dual-T4 FP8 tensor-parallel Kaggle case."""
    if tensor_parallel_size < 2:
        return False
    if "fp8" not in model.lower():
        return False
    if len(gpu_names) < tensor_parallel_size or len(gpu_memories) < tensor_parallel_size:
        return False

    selected_names = gpu_names[:tensor_parallel_size]
    selected_memories = gpu_memories[:tensor_parallel_size]
    if len(selected_names) < 2:
        return False
    if not all("t4" in name.lower() for name in selected_names):
        return False
    return all(memory >= DUAL_T4_MIN_BYTES for memory in selected_memories)


def gpu_inventory():
    import torch

    names = []
    memories = []
    for index in range(torch.cuda.device_count()):
        props = torch.cuda.get_device_properties(index)
        names.append(props.name)
        memories.append(props.total_memory)
    return names, memories


def main():
    import olmocr.pipeline as pipeline

    model = os.environ.get("OLMOCR_MODEL", "")
    tensor_parallel_size = int(os.environ.get("OLMOCR_TP_SIZE", "1"))
    names, memories = gpu_inventory()

    official_check_would_pass = bool(memories) and memories[0] >= OFFICIAL_MIN_BYTES
    if official_check_would_pass:
        return pipeline.cli_main()

    if can_bypass_memory_check(names, memories, tensor_parallel_size, model):
        logging.getLogger("olmocr.check").warning(
            "Bypassing olmOCR single-GPU 15GiB preflight for dual-T4 FP8 "
            "tensor-parallel run; vLLM will still enforce real memory limits."
        )
        pipeline.check_torch_gpu_available = lambda: None

    return pipeline.cli_main()


if __name__ == "__main__":
    sys.exit(main())
