import datetime
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from examples.erp.accounting.models import Account, AccountType, JournalEntry, JournalLine
from examples.erp.db import engine
from hyperadmin import Admin

router = APIRouter()


async def _get_pl_data(year: int) -> dict[str, Any]:
    """Query JournalLine aggregates for a given calendar year.

    Returns a dict with:
      - lines: list of {account_name, account_type, amount}
      - total_revenue: float
      - total_expenses: float
      - net_profit: float
    """
    start = datetime.date(year, 1, 1)
    end = datetime.date(year, 12, 31)

    async with AsyncSession(engine, expire_on_commit=False) as session:
        # Fetch journal lines for the year joined with entries and accounts
        stmt = (
            select(JournalLine, JournalEntry, Account)
            .join(JournalEntry, JournalLine.entry_id == JournalEntry.id)  # type: ignore[arg-type]  # SQLModel FK column not typed as InstrumentedAttribute
            .join(Account, JournalLine.account_id == Account.id)  # type: ignore[arg-type]  # SQLModel FK column not typed as InstrumentedAttribute
            .where(JournalEntry.date_posted >= start)
            .where(JournalEntry.date_posted <= end)
            .where(
                Account.account_type.in_([AccountType.REVENUE, AccountType.EXPENSE])  # type: ignore[attr-defined]  # AccountType is a str enum; .in_() available at runtime via SQLAlchemy column proxy
            )
        )
        result = await session.execute(stmt)
        rows = result.all()

    # Aggregate amounts per account
    account_totals: dict[int, dict[str, Any]] = {}
    for jl, _je, acc in rows:
        if acc.id not in account_totals:
            account_totals[acc.id] = {
                "account_name": acc.name,
                "account_type": acc.account_type,
                "amount": 0.0,
            }
        if acc.account_type == AccountType.REVENUE:
            # Revenue recognised on the credit side
            account_totals[acc.id]["amount"] += jl.credit - jl.debit
        else:
            # Expenses recognised on the debit side
            account_totals[acc.id]["amount"] += jl.debit - jl.credit

    lines = sorted(
        account_totals.values(), key=lambda x: (x["account_type"].value, x["account_name"])
    )

    total_revenue = sum(
        row["amount"] for row in lines if row["account_type"] == AccountType.REVENUE
    )
    total_expenses = sum(
        row["amount"] for row in lines if row["account_type"] == AccountType.EXPENSE
    )
    net_profit = total_revenue - total_expenses

    return {
        "lines": lines,
        "total_revenue": total_revenue,
        "total_expenses": total_expenses,
        "net_profit": net_profit,
    }


@router.get("/admin/reports/profit-loss", response_class=HTMLResponse)
async def profit_loss_report(
    request: Request,
    year: int | None = None,
) -> HTMLResponse:
    """Render the Annual Profit & Loss report for the given calendar year."""
    if year is None:
        year = datetime.datetime.now(tz=datetime.timezone.utc).date().year

    admin: Admin = request.app.state.admin
    pl_data = await _get_pl_data(year)
    report_url = str(request.url_for("profit_loss_report"))

    return admin.templates.TemplateResponse(
        request,
        "reports/profit_loss.html",
        {
            "year": year,
            "prev_year": year - 1,
            "next_year": year + 1,
            "report_url": report_url,
            "lines": pl_data["lines"],
            "total_revenue": pl_data["total_revenue"],
            "total_expenses": pl_data["total_expenses"],
            "net_profit": pl_data["net_profit"],
        },
    )
