"""CSV import functionality for the budget GUI application.

The functions in this module convert CSV files into sequences of
``Transaction`` instances.  They perform minimal normalisation and
assume a simple column format.  Duplicate detection is performed in
``AppState`` via transaction identifiers.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

import pandas as pd

from .models import Transaction


class TransactionImporter:
    """Import transactions from CSV files in a simple format."""

    def __init__(self, account_name: Optional[str] = None) -> None:
        self.account_name = account_name

    def import_csv(self, path: Path) -> Tuple[Transaction, ...]:
        """Load transactions from a CSV file.

        The CSV must contain at least the columns ``date``, ``account``,
        ``description``, ``amount`` and ``currency``.  The account
        column may be overridden by ``account_name`` provided at
        construction time.  Additional columns are ignored.

        Args:
            path: Path to the CSV file to import.

        Returns:
            A tuple of imported transactions.
        """
        df = pd.read_csv(path)
        required = {"date", "account", "description", "amount", "currency"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"CSV file {path} is missing required columns: {missing}")
        transactions: List[Transaction] = []
        for _, row in df.iterrows():
            # Parse date; pandas may return Timestamp
            dt = pd.to_datetime(row["date"]).date()
            account = self.account_name or str(row["account"])
            description = str(row["description"])
            amount = float(row["amount"])
            currency = str(row["currency"])
            tx_id = Transaction.make_id(dt, account, description, amount, currency)
            transactions.append(
                Transaction(
                    id=tx_id,
                    date=dt,
                    account=account,
                    description=description,
                    amount=amount,
                    currency=currency,
                    source_file=str(path),
                )
            )
        return tuple(transactions)