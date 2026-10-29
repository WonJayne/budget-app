"""CSV transaction import."""

from __future__ import annotations

from pathlib import Path
from math import isfinite

import pandas as pd

from .models import Transaction


class TransactionImporter:
    """Import normalized CSV files with date, account, description, amount, currency."""

    def import_csv(self, path: Path, account_name: str | None = None, import_source: str | None = None, *, source_file: str | None = None) -> tuple[Transaction, ...]:
        df = pd.read_csv(path)
        required = {"date", "account", "description", "amount", "currency"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"CSV file {path} is missing required columns: {', '.join(sorted(missing))}")

        source_name = source_file or path.name
        source_label = import_source or Path(source_name).stem or source_name
        transactions: list[Transaction] = []
        for row_number, (_, row) in enumerate(df.iterrows(), start=2):
            for field in ("date", "account", "description", "currency"):
                if field == "account" and account_name:
                    continue
                if pd.isna(row[field]) or not str(row[field]).strip():
                    raise ValueError(f"CSV row {row_number}: {field} is required")
            try:
                tx_date = pd.to_datetime(row["date"], errors="raise").date()
                amount = float(row["amount"])
                if pd.isna(tx_date) or not isfinite(amount):
                    raise ValueError("date and amount must be valid and finite")
            except (ValueError, TypeError, OverflowError) as exc:
                raise ValueError(f"CSV row {row_number}: invalid date or amount: {exc}") from exc
            account = account_name or str(row["account"])
            description = str(row["description"])
            currency = str(row["currency"])
            transactions.append(
                Transaction(
                    id=Transaction.make_id(tx_date, account, description, amount, currency),
                    date=tx_date,
                    account=account,
                    description=description,
                    amount=amount,
                    currency=currency,
                    source_file=source_name,
                    import_source=source_label,
                )
            )
        return tuple(transactions)
