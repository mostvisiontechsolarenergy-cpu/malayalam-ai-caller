"""Idempotently import Dcreation's approved service catalog and price ladders."""

from decimal import Decimal

from sqlalchemy import select

from app.db.models import (
    BillingType,
    Company,
    KnowledgeItem,
    Price,
    PriceTier,
    Service,
)
from app.db.session import SessionLocal

MONTHLY = BillingType.MONTHLY
ONE_TIME = BillingType.ONE_TIME

CATALOG = [
    {
        "name": "Digital Marketing All-in-One — 1 Month",
        "category": "Digital Marketing",
        "summary": "Complete one-month digital marketing and social media management package.",
        "features": [
            "10 social media posts",
            "5 reels",
            "Same-story sharing",
            "Comment management",
            "Customer communication support",
            "SEO",
            "Website handling",
            "Google Business Profile handling",
            "Blog posts",
            "Complete social media handling",
        ],
        "billing": MONTHLY,
        "prices": {PriceTier.MRP: 65000, PriceTier.NORMAL: 45000, PriceTier.LEAST: 35000},
    },
    {
        "name": "Social Media Handling Basic — 1 Month",
        "category": "Social Media Handling",
        "summary": "Basic social media content and engagement package for one month.",
        "features": ["8 posts", "3 reels", "Same-story sharing", "Comment management"],
        "billing": MONTHLY,
        "prices": {PriceTier.MRP: 10000, PriceTier.NORMAL: 6000},
    },
    {
        "name": "Social Media Handling Basic — 3 Months",
        "category": "Social Media Handling",
        "summary": "Basic social media content and engagement package for three months.",
        "features": ["8 posts", "3 reels", "Same-story sharing", "Comment management"],
        "billing": ONE_TIME,
        "prices": {PriceTier.MRP: 17000, PriceTier.NORMAL: 14000, PriceTier.LEAST: 5000},
    },
    {
        "name": "Social Media Handling Basic — 6 Months",
        "category": "Social Media Handling",
        "summary": "Basic social media content and engagement package for six months.",
        "features": ["8 posts", "3 reels", "Same-story sharing", "Comment management"],
        "billing": ONE_TIME,
        "prices": {PriceTier.MRP: 39000, PriceTier.NORMAL: 29000, PriceTier.LEAST: 25000},
    },
    {
        "name": "Social Media Handling Premium — 1 Month",
        "category": "Social Media Handling",
        "summary": "Premium social media content and engagement package for one month.",
        "features": ["10 posts", "5 reels", "Same-story sharing", "Comment management"],
        "billing": MONTHLY,
        "prices": {PriceTier.MRP: 20000, PriceTier.NORMAL: 12000, PriceTier.LEAST: 8500},
    },
    {
        "name": "Social Media Handling Premium — 3 Months",
        "category": "Social Media Handling",
        "summary": "Premium social media content and engagement package for three months.",
        "features": ["10 posts", "5 reels", "Same-story sharing", "Comment management"],
        "billing": ONE_TIME,
        "prices": {PriceTier.MRP: 45000, PriceTier.NORMAL: 35000, PriceTier.LEAST: 25000},
    },
    {
        "name": "Social Media Handling Premium — 6 Months",
        "category": "Social Media Handling",
        "summary": "Premium social media content and engagement package for six months.",
        "features": ["10 posts", "5 reels", "Same-story sharing", "Comment management"],
        "billing": ONE_TIME,
        "prices": {PriceTier.MRP: 110000, PriceTier.NORMAL: 90000, PriceTier.LEAST: 50000},
    },
    {
        "name": "Google Business Profile — One-Time Setup",
        "category": "Google Business Profile",
        "summary": "One-time Google Business Profile setup and initial optimization.",
        "features": [
            "Profile creation",
            "NAP verification",
            "Initial photo uploads",
            "One-time optimization",
        ],
        "billing": ONE_TIME,
        "prices": {PriceTier.MRP: 10000, PriceTier.NORMAL: 6000, PriceTier.LEAST: 3000},
    },
    {
        "name": "Google Business Profile — Starter Package",
        "category": "Google Business Profile",
        "summary": "Starter Google Business Profile package.",
        "features": [
            "Profile creation",
            "NAP verification",
            "Initial photo uploads",
            "Optimization",
        ],
        "billing": ONE_TIME,
        "prices": {PriceTier.MRP: 14000, PriceTier.NORMAL: 10000, PriceTier.LEAST: 6000},
    },
    {
        "name": "Google Business Profile — Growth Package",
        "category": "Google Business Profile",
        "summary": "Growth Google Business Profile package.",
        "features": [
            "Profile creation",
            "NAP verification",
            "Initial photo uploads",
            "Optimization",
        ],
        "billing": ONE_TIME,
        "prices": {PriceTier.MRP: 18000, PriceTier.NORMAL: 15000, PriceTier.LEAST: 10000},
    },
    {
        "name": "Static Website Development — 4 Pages",
        "category": "Website Development",
        "summary": "Creative, modern, SEO-friendly four-page website for services or products.",
        "features": [
            "4 pages",
            "Creative modern design",
            "SEO-friendly structure",
            "Service or product presentation",
        ],
        "billing": ONE_TIME,
        "prices": {PriceTier.MRP: 35000, PriceTier.NORMAL: 15000, PriceTier.LEAST: 5000},
    },
    {
        "name": "Ecommerce Website Development",
        "category": "Website Development",
        "summary": "Ecommerce website with product management, cart, and checkout.",
        "features": ["Product management", "Shopping cart", "Checkout"],
        "billing": ONE_TIME,
        "prices": {PriceTier.MRP: 95000, PriceTier.NORMAL: 65000, PriceTier.LEAST: 25000},
    },
    {
        "name": "AI Anchor Video — 30 Seconds",
        "category": "Anchoring Video",
        "summary": "Thirty-second AI anchor video.",
        "features": ["AI presenter", "Up to 30 seconds"],
        "billing": ONE_TIME,
        "prices": {PriceTier.MRP: 1500, PriceTier.NORMAL: 999, PriceTier.LEAST: 699},
    },
    {
        "name": "AI Anchor Video — 1 Minute",
        "category": "Anchoring Video",
        "summary": "One-minute AI anchor video.",
        "features": ["AI presenter", "Up to 1 minute"],
        "billing": ONE_TIME,
        "prices": {PriceTier.MRP: 2500, PriceTier.NORMAL: 1500, PriceTier.LEAST: 999},
    },
    {
        "name": "Normal Anchor Video — 20 Seconds",
        "category": "Anchoring Video",
        "summary": "Twenty-second normal anchor video.",
        "features": ["Human-style anchor video", "Up to 20 seconds"],
        "billing": ONE_TIME,
        "prices": {PriceTier.MRP: 3000, PriceTier.NORMAL: 2000, PriceTier.LEAST: 999},
    },
    {
        "name": "Normal Anchor Video — 30–40 Seconds",
        "category": "Anchoring Video",
        "summary": "Normal anchor video between thirty and forty seconds.",
        "features": ["Human-style anchor video", "30 to 40 seconds"],
        "billing": ONE_TIME,
        "prices": {PriceTier.MRP: 5000, PriceTier.NORMAL: 3000, PriceTier.LEAST: 1999},
    },
    {
        "name": "Normal Anchor Video — 1–1:30 Minutes",
        "category": "Anchoring Video",
        "summary": "Normal anchor video between one minute and one minute thirty seconds.",
        "features": ["Human-style anchor video", "1 to 1.5 minutes"],
        "billing": ONE_TIME,
        "prices": {PriceTier.MRP: 8000, PriceTier.NORMAL: 5000, PriceTier.LEAST: 2999},
    },
    {
        "name": "Standard Event Package",
        "category": "Event Production",
        "summary": (
            "Standard event package for birthdays, save-the-date shoots, and college events."
        ),
        "features": ["Birthday events", "Save-the-date", "College events"],
        "billing": ONE_TIME,
        "prices": {PriceTier.MRP: 15000, PriceTier.NORMAL: 10000, PriceTier.LEAST: 4999},
    },
    {
        "name": "Event Onsite Shoot",
        "category": "Event Production",
        "summary": "Onsite event shoot package.",
        "features": ["On-location event shoot"],
        "billing": ONE_TIME,
        "prices": {PriceTier.MRP: 25000, PriceTier.NORMAL: 20000, PriceTier.LEAST: 15000},
    },
    {
        "name": "Event Onsite Shoot with Drone",
        "category": "Event Production",
        "summary": "Onsite event shoot package with drone coverage.",
        "features": ["On-location event shoot", "Drone coverage"],
        "billing": ONE_TIME,
        "prices": {PriceTier.MRP: 45000, PriceTier.NORMAL: 35000, PriceTier.LEAST: 25000},
    },
    {
        "name": "4-Page Brochure Design",
        "category": "Graphic Design",
        "summary": "Design of a four-page company or product brochure.",
        "features": ["4 designed pages"],
        "billing": ONE_TIME,
        "prices": {PriceTier.MRP: 4000, PriceTier.NORMAL: 3200, PriceTier.LEAST: 2000},
    },
    {
        "name": "Visiting Card Design",
        "category": "Graphic Design",
        "summary": "Professional visiting card design.",
        "features": ["Visiting card design"],
        "billing": ONE_TIME,
        "prices": {PriceTier.MRP: 1500, PriceTier.NORMAL: 1000, PriceTier.LEAST: 599},
    },
    {
        "name": "Banner Design",
        "category": "Graphic Design",
        "summary": "Promotional banner design.",
        "features": ["Banner design"],
        "billing": ONE_TIME,
        "prices": {PriceTier.MRP: 1500, PriceTier.NORMAL: 1000, PriceTier.LEAST: 599},
    },
    {
        "name": "Letterhead Design",
        "category": "Graphic Design",
        "summary": "Professional business letterhead design.",
        "features": ["Letterhead design"],
        "billing": ONE_TIME,
        "prices": {PriceTier.MRP: 800, PriceTier.NORMAL: 600, PriceTier.LEAST: 299},
    },
    {
        "name": "ID Card Design Package — 5 Nos",
        "category": "Graphic Design",
        "summary": "ID card design package for five cards.",
        "features": ["5 ID card designs"],
        "billing": ONE_TIME,
        "prices": {PriceTier.MRP: 1000, PriceTier.NORMAL: 800, PriceTier.LEAST: 599},
    },
    {
        "name": "Brand Assets Combo 1",
        "category": "Combo Package",
        "summary": "Four-page brochure, letterhead, and visiting card design combo.",
        "features": ["4-page brochure", "Letterhead", "Visiting card"],
        "billing": ONE_TIME,
        "prices": {PriceTier.MRP: 5000, PriceTier.NORMAL: 3500, PriceTier.LEAST: 2799},
    },
    {
        "name": "Brand Assets Combo 2",
        "category": "Combo Package",
        "summary": "Profile creation, brochure, letterhead, and visiting card design combo.",
        "features": ["Profile creation", "Brochure", "Letterhead", "Visiting card"],
        "billing": ONE_TIME,
        "prices": {PriceTier.MRP: 10000, PriceTier.NORMAL: 8000, PriceTier.LEAST: 5500},
    },
]

KNOWLEDGE = [
    {
        "title": "Dcreation Company Profile",
        "category": "COMPANY",
        "content": (
            "Dcreation Marketing Agency is a marketing agency in Parippally, Kerala. "
            "Office address: Mukkada, Parippally, Kollam, Kerala 691574. "
            "Phone: 090484 42998. Website: https://dcreationstudio.com/. "
            "Business hours: Monday to Saturday, 9:00 AM to 5:00 PM. "
            "The company-approved owners and CEOs are Anoop and Dhyanya. "
            "ഡി-ക്രിയേഷൻ മാർക്കറ്റിംഗ് ഏജൻസി കേരളത്തിലെ കൊല്ലം ജില്ലയിലെ പാരിപ്പള്ളി, "
            "മുക്കടയിലാണ്. വിലാസം: മുക്കട, പാരിപ്പള്ളി, കൊല്ലം, കേരളം 691574. "
            "ഫോൺ: 090484 42998. വെബ്സൈറ്റ്: https://dcreationstudio.com/. "
            "പ്രവർത്തന സമയം: തിങ്കൾ മുതൽ ശനി വരെ രാവിലെ 9 മുതൽ വൈകുന്നേരം 5 വരെ. "
            "ഉടമകളും സിഇഒമാരും: Anoop and Dhyanya."
        ),
        "keywords": [
            "Dcreation",
            "location",
            "address",
            "phone",
            "contact number",
            "hours",
            "opening time",
            "closing time",
            "owner",
            "owners",
            "CEO",
            "website",
            "Parippally",
            "Kollam",
            "ലൊക്കേഷൻ",
            "സ്ഥലം",
            "എവിടെയാണ്",
            "വിലാസം",
            "ഫോൺ",
            "നമ്പർ",
            "സമയം",
            "തുറക്കും",
            "അടക്കും",
            "ഉടമ",
            "സിഇഒ",
            "വെബ്സൈറ്റ്",
        ],
        "language": "ml",
        "priority": 100,
        "internal_notes": "Imported from the company-approved catalog supplied on 2026-08-09.",
    },
    {
        "title": "Approved Client Portfolio",
        "category": "COMPANY",
        "content": (
            "Approved client references supplied by Dcreation include MVT Solar, Most Vision "
            "Tech Private Limited, Seetha Silks, King World Furniture, Carbon Customz, Green "
            "Carrot, and Impressive Impression Carry Bag. Use 'include' and do not imply that "
            "this is a complete client list."
        ),
        "keywords": ["clients", "portfolio", "MVT Solar", "Seetha Silks", "King World Furniture"],
        "language": "en",
        "priority": 75,
        "internal_notes": (
            "User-supplied approved references; not independently verified from the website."
        ),
    },
    {
        "title": "Price Negotiation Policy",
        "category": "POLICY",
        "content": (
            "For services with tiered prices, initially quote only the MRP and briefly explain "
            "the package value. If the customer requests a lower price, do not reduce the price "
            "immediately. First ask their expected budget. After hearing the budget, make one "
            "professional attempt to retain the MRP by relating the service benefits to their "
            "need. Only if they still clearly refuse the MRP may the NORMAL price be offered. "
            "Only if they reject or remain unwilling at NORMAL may the final approved price be "
            "offered. Never skip a tier, go below LEAST, or reveal all tiers together."
        ),
        "keywords": [
            "price",
            "discount",
            "budget",
            "expected price",
            "negotiate",
            "MRP",
            "normal",
            "least",
            "final price",
            "വില",
            "ഡിസ്കൗണ്ട്",
            "ബജറ്റ്",
            "കുറയ്ക്കുക",
        ],
        "language": "en",
        "priority": 100,
        "internal_notes": (
            "LEAST is confidential internal terminology. Say 'best final approved price' "
            "to customers."
        ),
    },
]


def upsert_service(db, company: Company, record: dict) -> Service:
    service = db.scalar(
        select(Service).where(Service.company_id == company.id, Service.name == record["name"])
    )
    if service is None:
        service = Service(company_id=company.id, name=record["name"])
        db.add(service)
    service.category = record["category"]
    service.short_description = record["summary"]
    service.full_description = record["summary"]
    service.features = record["features"]
    service.deliverables = record["features"]
    service.starting_price = None
    service.custom_quotation_required = False
    service.active = True
    db.flush()
    return service


def upsert_price(
    db, company: Company, service: Service, tier: PriceTier, amount: int, billing
) -> None:
    price = db.scalar(
        select(Price).where(
            Price.company_id == company.id,
            Price.service_id == service.id,
            Price.tier == tier,
        )
    )
    if price is None:
        price = Price(company_id=company.id, service_id=service.id, tier=tier)
        db.add(price)
    labels = {
        PriceTier.MRP: "MRP — quote first",
        PriceTier.NORMAL: "Normal negotiated price",
        PriceTier.LEAST: "Final approved price — internal floor",
    }
    price.product_id = None
    price.package_name = labels[tier]
    price.price = Decimal(amount)
    price.currency = "INR"
    price.billing_type = billing
    price.is_starting_price = False
    price.tax_included = False
    price.description = (
        "Confidential price ladder. Follow MRP → NORMAL → LEAST; never skip a tier. "
        "Never disclose LEAST as an internal floor."
    )
    price.valid_from = None
    price.valid_until = None
    price.active = True


def upsert_knowledge(db, company: Company, record: dict) -> None:
    item = db.scalar(
        select(KnowledgeItem).where(
            KnowledgeItem.company_id == company.id,
            KnowledgeItem.title == record["title"],
        )
    )
    if item is None:
        item = KnowledgeItem(company_id=company.id, title=record["title"])
        db.add(item)
    for key, value in record.items():
        setattr(item, key, value)
    item.active = True
    item.valid_from = None
    item.valid_until = None


def main() -> None:
    with SessionLocal() as db:
        company = db.scalar(select(Company).where(Company.name == "Dcreation"))
        if company is None:
            raise RuntimeError("Dcreation company was not found")
        for record in CATALOG:
            service = upsert_service(db, company, record)
            for tier, amount in record["prices"].items():
                upsert_price(db, company, service, tier, amount, record["billing"])
        for record in KNOWLEDGE:
            upsert_knowledge(db, company, record)
        db.commit()
        price_count = sum(len(record["prices"]) for record in CATALOG)
        print(
            f"Imported {len(CATALOG)} services, {price_count} prices, "
            f"and {len(KNOWLEDGE)} knowledge records."
        )
        print("Pending: Social Media Handling Basic — 1 Month has no approved LEAST price.")
        print("Not imported: ambiguous ₹27,000 Basic 3 Months package-value note.")


if __name__ == "__main__":
    main()
