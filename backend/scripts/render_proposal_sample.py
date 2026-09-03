from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from app.services.proposals import build_proposal_pdf

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "pdf" / "loom-solar-web-development-proposal.pdf"

proposal = SimpleNamespace(
    proposal_number="PROP-20260815-LOOM",
    proposal_date=date(2026, 8, 15),
    valid_until=date(2026, 8, 22),
    project_start_date=date(2026, 8, 25),
    project_end_date=date(2026, 9, 15),
    currency="INR",
    subtotal=Decimal("15000.00"),
    total_amount=Decimal("15000.00"),
    notes="Demo proposal based on the approved Static Website Development package.",
    terms=(
        "100% advance payment. Delivery begins after content, access and scope approval "
        "are received."
    ),
)
client = SimpleNamespace(
    name="Loom Solar",
    business_name="Loom Solar",
    location="India",
    phone="+91 00000 00000",
    email="contact@example.com",
)
company = SimpleNamespace(name="Dcreation")
items = [
    SimpleNamespace(
        line_number=1,
        item_name="Static Website Development - 4 Pages",
        package_name="Normal Package",
        description=(
            "Creative, modern, SEO-friendly four-page website for services or products.\n"
            "4 responsive pages\n"
            "Creative modern design\n"
            "SEO-friendly structure\n"
            "Service or product presentation\n"
            "Mobile and desktop optimization\n"
            "Contact enquiry integration\n"
            "Testing and launch support"
        ),
        quantity=Decimal("1"),
        unit_price=Decimal("15000.00"),
        amount=Decimal("15000.00"),
        currency="INR",
    ),
]

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_bytes(
    build_proposal_pdf(proposal=proposal, client=client, company=company, items=items)
)
print(OUTPUT)
