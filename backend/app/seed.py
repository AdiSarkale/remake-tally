"""Seed demo users, masters and opening stock. Run: python -m app.seed"""

from datetime import date, timedelta

from app import models
from app.core.security import hash_password
from app.db.session import Base, SessionLocal, engine
from app.models import ItemKind, MovementType
from app.services.inventory import apply_movement

USERS = [
    ("admin", "Ravi Kulkarni", "admin123", models.Role.admin),
    ("accounts", "Priya Deshmukh", "accounts123", models.Role.accountant),
    ("operator", "Imran Shaikh", "operator123", models.Role.operator),
]


def run() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(models.User).count():
            print("Database already seeded.")
            return

        for username, full_name, password, role in USERS:
            db.add(
                models.User(
                    username=username,
                    full_name=full_name,
                    password_hash=hash_password(password),
                    role=role,
                )
            )

        db.add(models.CompanySettings(id=1, name="Shreeji Precision Works", invoice_prefix="SPW"))

        for kind, name in [("customer", "Vardhman Auto Parts"), ("supplier", "Bharat Steel Traders")]:
            db.add(models.Party(kind=kind, name=name))

        products = [
            models.Product(code="FG-001", name="Machined Shaft 150mm", cost_price=180, selling_price=260, min_stock=100),
            models.Product(code="FG-002", name="Sheet Metal Bracket A", cost_price=95, selling_price=145, min_stock=120),
        ]
        materials = [
            models.RawMaterial(name="Aluminium Rod 25mm", unit="KG", cost=210, min_stock=200),
            models.RawMaterial(name="MS Sheet 2mm", unit="KG", cost=68, min_stock=300),
        ]
        scrap_types = [
            models.ScrapType(name="Aluminium Turnings", unit="KG", selling_rate=95),
            models.ScrapType(name="MS Offcuts", unit="KG", selling_rate=32),
        ]
        db.add_all(products + materials + scrap_types)
        db.flush()

        opening = date.today() - timedelta(days=14)
        for material in materials:
            apply_movement(
                db,
                kind=ItemKind.material,
                item_id=material.id,
                movement_type=MovementType.IN,
                quantity=1500,
                reference="OPENING",
                reason="Opening stock",
                entry_date=opening,
                user_id="seed",
            )
        for product in products:
            apply_movement(
                db,
                kind=ItemKind.product,
                item_id=product.id,
                movement_type=MovementType.IN,
                quantity=400,
                reference="OPENING",
                reason="Opening stock",
                entry_date=opening,
                user_id="seed",
            )

        db.commit()
        print("Seeded demo data.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
