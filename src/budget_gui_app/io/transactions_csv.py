"""CSV export for the current merged transaction state."""

from __future__ import annotations

import csv
import io

from ..core.models import Transaction

CSV_COLUMNS = (
    "id",
    "date",
    "account",
    "description",
    "amount",
    "currency",
    "category",
    "owner",
    "assignment_source",
    "ignored",
    "source_kind",
    "source_file",
    "import_source",
    "cash_flow_type",
    "transfer_direction",
    "transfer_group_id",
    "transfer_note",
)


def transactions_to_csv(transactions: tuple[Transaction, ...]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=CSV_COLUMNS)
    writer.writeheader()
    for tx in transactions:
        writer.writerow(
            {
                "id": tx.id,
                "date": tx.date.isoformat(),
                "account": tx.account,
                "description": tx.description,
                "amount": f"{tx.amount:.2f}",
                "currency": tx.currency,
                "category": tx.category or "",
                "owner": tx.owner or "",
                "assignment_source": tx.assignment_source or "",
                "ignored": "true" if tx.ignored else "false",
                "source_kind": tx.source_kind,
                "source_file": tx.source_file or "",
                "import_source": tx.stable_import_source or "",
                "cash_flow_type": tx.flow_type or "",
                "transfer_direction": tx.transfer_direction or "",
                "transfer_group_id": tx.transfer_group_id or "",
                "transfer_note": tx.transfer_note or "",
            }
        )
    return output.getvalue()
