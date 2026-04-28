from datetime import datetime, timedelta
from auth import hash_password

SAMPLE_EXPENSES = [
    {"title": "Team lunch - product sync", "amount": 127.50, "category": "Meals & Entertainment", "vendor": "The Slanted Door", "latitude": 37.7955, "longitude": -122.3937, "city": "San Francisco", "date": datetime.now() - timedelta(days=2), "tax_deductible": True, "ai_note": "Business meal with product team — 50% deductible under IRS §274"},
    {"title": "Cloud hosting - AWS", "amount": 342.18, "category": "Software & Tech", "vendor": "Amazon Web Services", "latitude": 37.3861, "longitude": -122.0839, "city": "Sunnyvale", "date": datetime.now() - timedelta(days=5), "tax_deductible": True, "ai_note": "Fully deductible business infrastructure expense"},
    {"title": "Flight to NYC - client meeting", "amount": 489.00, "category": "Travel", "vendor": "United Airlines", "latitude": 37.6213, "longitude": -122.3790, "city": "San Francisco SFO", "date": datetime.now() - timedelta(days=8), "tax_deductible": True, "ai_note": "Fully deductible business travel — keep boarding pass"},
    {"title": "Hotel - client visit NYC", "amount": 315.00, "category": "Travel", "vendor": "Marriott Midtown", "latitude": 40.7580, "longitude": -73.9855, "city": "New York", "date": datetime.now() - timedelta(days=7), "tax_deductible": True, "ai_note": "Fully deductible lodging for business travel"},
    {"title": "Office supplies - Q1", "amount": 89.47, "category": "Office Supplies", "vendor": "Staples", "latitude": 37.5630, "longitude": -122.0530, "city": "Fremont", "date": datetime.now() - timedelta(days=12), "tax_deductible": True, "ai_note": "Fully deductible ordinary business supplies"},
    {"title": "Client dinner - deal close", "amount": 203.75, "category": "Meals & Entertainment", "vendor": "Gary Danko", "latitude": 37.8057, "longitude": -122.4218, "city": "San Francisco", "date": datetime.now() - timedelta(days=3), "tax_deductible": True, "ai_note": "Client entertainment — 50% deductible, document business purpose"},
    {"title": "Uber - airport to office", "amount": 34.20, "category": "Transportation", "vendor": "Uber", "latitude": 37.6879, "longitude": -122.4702, "city": "Daly City", "date": datetime.now() - timedelta(days=8), "tax_deductible": True, "ai_note": "Business transportation — fully deductible"},
    {"title": "GitHub Copilot subscription", "amount": 19.00, "category": "Software & Tech", "vendor": "GitHub", "latitude": 37.7826, "longitude": -122.3916, "city": "San Francisco", "date": datetime.now() - timedelta(days=15), "tax_deductible": True, "ai_note": "Software subscription for business — fully deductible"},
    {"title": "Conference registration - Dreamforce", "amount": 1299.00, "category": "Professional Development", "vendor": "Salesforce", "latitude": 37.7840, "longitude": -122.4000, "city": "San Francisco", "date": datetime.now() - timedelta(days=20), "tax_deductible": True, "ai_note": "Professional conference directly related to business — fully deductible"},
    {"title": "Coffee meeting - potential partner", "amount": 18.50, "category": "Meals & Entertainment", "vendor": "Blue Bottle Coffee", "latitude": 37.7886, "longitude": -122.4008, "city": "San Francisco", "date": datetime.now() - timedelta(days=1), "tax_deductible": True, "ai_note": "Business meeting — 50% deductible, note the business purpose"},
    {"title": "Parking - downtown meetings", "amount": 42.00, "category": "Transportation", "vendor": "SF Parking", "latitude": 37.7897, "longitude": -122.3972, "city": "San Francisco", "date": datetime.now() - timedelta(days=4), "tax_deductible": True, "ai_note": "Business parking — fully deductible"},
    {"title": "Team building event", "amount": 560.00, "category": "Meals & Entertainment", "vendor": "Escape Room SF", "latitude": 37.7831, "longitude": -122.4039, "city": "San Francisco", "date": datetime.now() - timedelta(days=10), "tax_deductible": False, "ai_note": "Team activities are generally not deductible under current tax law"},
]


def seed_database(db):
    from database import Company, User, Expense

    # Skip if already seeded
    if db.query(Company).first():
        return

    # Create demo company
    company = Company(name="Demo Company", slug="demo-company")
    db.add(company)
    db.flush()

    # Create demo owner
    owner = User(
        email="demo@geoexpense.com",
        name="Demo User",
        hashed_password=hash_password("demo1234"),
        company_id=company.id,
        role="owner",
    )
    db.add(owner)
    db.flush()

    # Seed expenses assigned to demo company + owner
    for data in SAMPLE_EXPENSES:
        expense = Expense(
            **data,
            status="approved",
            user_id=owner.id,
            company_id=company.id,
        )
        db.add(expense)

    db.commit()
