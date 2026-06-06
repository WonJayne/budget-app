"""Build Plotly Sankey figures from current transaction state."""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable, Mapping

import plotly.graph_objects as go

from .models import CategoryStyle, Transaction, flow_type_for_amount
from .periods import PeriodFilter
from .summaries import cash_flow_totals

DEFAULT_NODE_COLOUR = "#9ca3af"
DEFAULT_LINK_COLOUR = "rgba(156, 163, 175, 0.35)"
POOL_NODE = "Household pool"
POTENTIAL_SAVINGS_NODE = "Potential savings"
DEFICIT_NODE = "Deficit"


class SankeyBuilder:
    def build(
        self,
        transactions: Iterable[Transaction],
        styles: Mapping[str, CategoryStyle],
        *,
        include_ignored: bool,
        month: str | None = None,
        owner: str | None = None,
        currency: str | None = None,
        period: PeriodFilter | None = None,
        include_inflows: bool | None = None,
        include_income: bool | None = None,
    ) -> go.Figure:
        if include_inflows is None:
            include_inflows = True if include_income is None else include_income
        filtered = [
            transaction
            for transaction in transactions
            if self._included(transaction, include_inflows, include_ignored, month, owner, currency, period)
        ]

        node_index: dict[str, int] = {}
        labels: list[str] = []
        colours: list[str] = []

        def node(label: str) -> int:
            if label not in node_index:
                node_index[label] = len(labels)
                labels.append(label)
                colours.append(styles.get(label, CategoryStyle(label)).colour or DEFAULT_NODE_COLOUR)
            return node_index[label]

        def category_colour(label: str) -> str:
            return styles.get(label, CategoryStyle(label)).colour or DEFAULT_NODE_COLOUR

        flows: defaultdict[tuple[int, int], float] = defaultdict(float)
        flow_counts: defaultdict[tuple[int, int], int] = defaultdict(int)
        flow_share_basis: dict[tuple[int, int], str] = {}
        link_colours_by_pair: dict[tuple[int, int], str] = {}

        def add_flow(source_label: str, target_label: str, value: float, colour: str = DEFAULT_LINK_COLOUR, *, share_basis: str = "flow", count: int = 0) -> None:
            if value <= 0:
                return
            source = node(source_label)
            target = node(target_label)
            flows[(source, target)] += value
            flow_counts[(source, target)] += count
            flow_share_basis[(source, target)] = share_basis
            link_colours_by_pair[(source, target)] = colour or DEFAULT_LINK_COLOUR

        for transaction in filtered:
            flow_type = flow_type_for_amount(transaction.amount)
            if flow_type == "inflow":
                category = transaction.category or "Uncategorised inflow"
                owner_name = transaction.owner or "Unassigned inflow"
                owner_node = f"{owner_name} inflow" if owner_name != "Unassigned inflow" else owner_name
                add_flow(category, owner_node, transaction.amount, category_colour(category), share_basis="inflow", count=1)
                add_flow(owner_node, POOL_NODE, transaction.amount, share_basis="inflow", count=1)
            elif flow_type == "outflow":
                category = transaction.category or "Uncategorised outflow"
                owner_name = transaction.owner or "Unassigned outflow"
                owner_node = f"{owner_name} outflow" if owner_name != "Unassigned outflow" else owner_name
                value = abs(transaction.amount)
                add_flow(POOL_NODE, owner_node, value, share_basis="outflow", count=1)
                add_flow(owner_node, category, value, category_colour(category), share_basis="outflow", count=1)

        totals = cash_flow_totals(filtered)
        if totals.balance > 0:
            add_flow(POOL_NODE, POTENTIAL_SAVINGS_NODE, totals.balance, share_basis="inflow")
        elif totals.balance < 0:
            add_flow(DEFICIT_NODE, POOL_NODE, abs(totals.balance), share_basis="outflow")

        sources = [source for source, _ in flows]
        targets = [target for _, target in flows]
        values = [value for value in flows.values()]
        link_colours = [link_colours_by_pair.get(pair, DEFAULT_LINK_COLOUR) for pair in flows]
        customdata = []
        for pair, value in flows.items():
            source_label = labels[pair[0]]
            target_label = labels[pair[1]]
            basis = flow_share_basis.get(pair, "flow")
            denominator = totals.total_inflow if basis == "inflow" else totals.total_outflow if basis == "outflow" else 0.0
            share = value / denominator if denominator else 0.0
            customdata.append((source_label, target_label, f"CHF {value:,.2f}", f"Share of total {basis}: {share:.1%}", flow_counts.get(pair, 0)))

        fig = go.Figure(
            go.Sankey(
                arrangement="snap",
                node={"label": labels, "color": colours, "pad": 12, "thickness": 16},
                link={
                    "source": sources,
                    "target": targets,
                    "value": values,
                    "color": link_colours,
                    "customdata": customdata,
                    "hovertemplate": "%{customdata[0]} → %{customdata[1]}<br>%{customdata[2]}<br>%{customdata[3]}<br>Transactions: %{customdata[4]}<extra></extra>",
                },
            )
        )
        fig.update_layout(title_text="Household Cash-Flow Sankey", font={"size": 12}, margin={"l": 8, "r": 8, "t": 36, "b": 8}, height=560)
        return fig

    @staticmethod
    def _included(
        transaction: Transaction,
        include_inflows: bool,
        include_ignored: bool,
        month: str | None = None,
        owner: str | None = None,
        currency: str | None = None,
        period: PeriodFilter | None = None,
    ) -> bool:
        flow_type = flow_type_for_amount(transaction.amount)
        if flow_type is None:
            return False
        if not include_ignored and transaction.ignored:
            return False
        if period is not None and not period.includes(transaction):
            return False
        if period is None and month and transaction.date.strftime("%Y-%m") != month:
            return False
        if owner and transaction.owner != owner:
            return False
        if currency and transaction.currency != currency:
            return False
        if not include_inflows and flow_type == "inflow":
            return False
        return True
