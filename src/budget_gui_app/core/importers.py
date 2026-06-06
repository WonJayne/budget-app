"""CSV transaction import."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .models import Transaction


class TransactionImporter:
    """Import normalized CSV files with date, account, description, amount, currency."""

    def import_csv(self, path: Path, account_name: str | None = None) -> tuple[Transaction, ...]:
        df = pd.read_csv(path)
        required = {"date", "account", "description", "amount", "currency"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"CSV file {path} is missing required columns: {', '.join(sorted(missing))}")

        transactions: list[Transaction] = []
        for _, row in df.iterrows():
            tx_date = pd.to_datetime(row["date"]).date()
            account = account_name or str(row["account"])
            description = str(row["description"])
            amount = float(row["amount"])
            currency = str(row["currency"])
            transactions.append(
                Transaction(
                    id=Transaction.make_id(tx_date, account, description, amount, currency),
                    date=tx_date,
                    account=account,
                    description=description,
                    amount=amount,
                    currency=currency,
                    source_file=path.name,
                )
            )
        return tuple(transactions)
