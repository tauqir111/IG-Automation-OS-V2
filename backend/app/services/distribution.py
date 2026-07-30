"""Job planning + distribution logic.

Given a distribution mode, an ordered list of file IDs and a target account
quantity, compute the expected number of jobs. The actual (account_id, file_id)
pairs are only materialised at campaign-run time in a later phase; this module
gives us the count needed for the summary/estimation.
"""
from typing import List


def estimate_jobs(mode: str, files: List[int], account_quantity: int) -> int:
    """Return the expected number of jobs for this distribution mode."""
    n_files = len(files)
    if account_quantity <= 0 or n_files <= 0:
        return 0

    if mode == "same":
        # 1 file (first) posted to every account
        return account_quantity
    if mode == "one_per_account":
        # min(files, accounts) — extra files/accounts are unused
        return min(n_files, account_quantity)
    if mode == "round_robin":
        # Every account gets one file, cycling through files
        return account_quantity
    return 0


def plan_pairs(mode: str, file_ids: List[int], account_ids: List[int]):
    """Yield (account_id, file_id) tuples for the given mode.

    Reserved for Phase 3 (queue builder). Kept here so distribution logic
    lives in one place.
    """
    n_files = len(file_ids)
    if not file_ids or not account_ids:
        return

    if mode == "same":
        for acc in account_ids:
            yield (acc, file_ids[0])
    elif mode == "one_per_account":
        for i in range(min(n_files, len(account_ids))):
            yield (account_ids[i], file_ids[i])
    elif mode == "round_robin":
        for i, acc in enumerate(account_ids):
            yield (acc, file_ids[i % n_files])
