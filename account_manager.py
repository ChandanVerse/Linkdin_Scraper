"""
LinkedIn Account Manager — simple round-robin rotation.

Rules:
  - Rotate to the next account after every full round of keyword searches
  - Always cycle in order: 0 → 1 → 2 → 0 → 1 → 2 ...
  - If an account hits a CAPTCHA/challenge it is cooled down for COOLDOWN_HOURS
  - Cooled-down accounts are skipped in rotation (not used until cooldown expires)
  - If ALL accounts are on cooldown, search without login for that round
"""

import json
import os
import random
import time
from datetime import datetime, timedelta

COOLDOWN_HOURS  = float(os.environ.get("ACCOUNT_COOLDOWN_HOURS", "2.0"))
MIN_ROTATE_DELAY = float(os.environ.get("MIN_ROTATION_DELAY", "8.0"))
MAX_ROTATE_DELAY = float(os.environ.get("MAX_ROTATION_DELAY", "20.0"))

STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "account_state.json")


class AccountManager:
    """Round-robin account pool — rotates once per full keyword round."""

    def __init__(self, accounts: list[dict]):
        self.accounts = accounts
        self._state = self._load_state()
        # Start at the first non-cooled account
        self._current_idx = self._next_available(start=-1)

    # ── State ──────────────────────────────────────────────────────────

    def _load_state(self) -> dict:
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE) as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_state(self):
        with open(STATE_FILE, "w") as f:
            json.dump(self._state, f, indent=2)

    def _acc_state(self, idx: int) -> dict:
        key = str(idx)
        if key not in self._state:
            self._state[key] = {
                "last_used": None,
                "cooldown_until": None,
                "challenges": 0,
            }
        return self._state[key]

    # ── Cooldown ───────────────────────────────────────────────────────

    def _is_on_cooldown(self, idx: int) -> bool:
        cd = self._acc_state(idx).get("cooldown_until")
        if not cd:
            return False
        return datetime.now() < datetime.fromisoformat(cd)

    def _next_available(self, start: int) -> int:
        """
        Return the next account index after `start` that is NOT on cooldown.
        Wraps around. Returns -1 (no account) if all are on cooldown.
        """
        n = len(self.accounts)
        for offset in range(1, n + 1):
            idx = (start + offset) % n
            if not self._is_on_cooldown(idx):
                return idx
        return -1  # all cooled down

    # ── Public API ─────────────────────────────────────────────────────

    @property
    def current_idx(self) -> int:
        return self._current_idx

    @property
    def current(self) -> dict | None:
        """None when all accounts are on cooldown (run without login)."""
        if self._current_idx == -1:
            return None
        return self.accounts[self._current_idx]

    @property
    def profile_suffix(self) -> str:
        if self._current_idx == -1:
            return "li_guest"
        return f"li_{self._current_idx}"

    def rotate(self):
        """
        Advance to the next account in round-robin order.
        Pauses briefly to appear human. Call once per full keyword round.
        """
        old = self.current
        old_name = old.get("name", f"Account {self._current_idx}") if old else "Guest"

        delay = random.uniform(MIN_ROTATE_DELAY, MAX_ROTATE_DELAY)
        print(f"[AccountManager] Round complete for {old_name}. "
              f"Rotating in {delay:.1f}s...")
        time.sleep(delay)

        self._current_idx = self._next_available(self._current_idx)

        if self._current_idx == -1:
            print("[AccountManager] ⚠  All accounts on cooldown — "
                  "next round will run without login.")
        else:
            new_name = self.accounts[self._current_idx].get(
                "name", f"Account {self._current_idx}"
            )
            print(f"[AccountManager] Now using: {new_name} "
                  f"(profile: chrome_profile_{self.profile_suffix})")

    def mark_challenge(self):
        """
        Called when the current account hits a CAPTCHA or checkpoint.
        Cools it down and immediately rotates to the next available account.
        """
        if self._current_idx == -1:
            return  # already guest, nothing to cool down

        st = self._acc_state(self._current_idx)
        st["challenges"] = st.get("challenges", 0) + 1
        st["cooldown_until"] = (
            datetime.now() + timedelta(hours=COOLDOWN_HOURS)
        ).isoformat()
        name = self.accounts[self._current_idx].get(
            "name", f"Account {self._current_idx}"
        )
        print(f"[AccountManager] ⚠  Challenge on {name}! "
              f"Cooling down for {COOLDOWN_HOURS}h.")
        self._save_state()

        # Immediately jump to next available (no delay — we need out fast)
        self._current_idx = self._next_available(self._current_idx)
        if self._current_idx == -1:
            print("[AccountManager] All accounts on cooldown — switching to guest mode.")
        else:
            new_name = self.accounts[self._current_idx].get(
                "name", f"Account {self._current_idx}"
            )
            print(f"[AccountManager] Switched to: {new_name}")

    def record_used(self):
        """Call after each round to track last-used timestamp."""
        if self._current_idx == -1:
            return
        self._acc_state(self._current_idx)["last_used"] = datetime.now().isoformat()
        self._save_state()

    def status(self) -> str:
        lines = ["[AccountManager] Account pool:"]
        for i, acc in enumerate(self.accounts):
            st = self._acc_state(i)
            badge = "[COOLDOWN]" if self._is_on_cooldown(i) else "[OK]"
            marker = " << current" if i == self._current_idx else ""
            cd_str = ""
            if self._is_on_cooldown(i):
                remaining = (
                    datetime.fromisoformat(st["cooldown_until"]) - datetime.now()
                )
                mins = int(remaining.total_seconds() / 60)
                cd_str = f" ({mins}m remaining)"
            lines.append(
                f"  [{i}] {acc.get('name', acc['email'])} "
                f"{badge}{cd_str}{marker}"
            )
        if self._current_idx == -1:
            lines.append("  [guest] No login ◄ current")
        return "\n".join(lines)