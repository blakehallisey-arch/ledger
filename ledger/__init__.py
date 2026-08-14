"""ledger — a memory of what you did with a stateless agent's advice.

The record is markdown, one file per agent. The Action and Outcome slots are
human-only; see ledger/store.py for why that block lives in the store.
"""

from .store import (  # noqa: F401
    ACTIONS,
    HUMAN_ONLY,
    OUTCOMES,
    Entry,
    HumanOnlyField,
    Ledger,
    LedgerError,
    append,
    load,
    parse,
    render,
    rule,
    save,
)

__version__ = "0.1.0"
