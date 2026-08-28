"""reconcile live schema and procurement baseline

Revision ID: b10b63f2a9fb
Revises: 137bed0425f2
Create Date: 2026-08-25 11:23:30.895835
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b10b63f2a9fb"
down_revision: Union[str, Sequence[str], None] = "137bed0425f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _sql(sql: str) -> None:
    op.execute(sa.text(sql))


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Company settings
    # ------------------------------------------------------------------

    _sql(
        """
        ALTER TABLE company_settings
        ADD COLUMN IF NOT EXISTS gst_number VARCHAR(32)
        """
    )

    _sql(
        """
        ALTER TABLE company_settings
        ADD COLUMN IF NOT EXISTS address TEXT
        """
    )

    # ------------------------------------------------------------------
    # 2. Raw materials
    # ------------------------------------------------------------------

    _sql(
        """
        ALTER TABLE raw_materials
        ADD COLUMN IF NOT EXISTS code VARCHAR(32)
        """
    )

    _sql(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND indexname = 'ix_raw_materials_code'
            ) THEN
                CREATE UNIQUE INDEX ix_raw_materials_code
                ON raw_materials (code);
            END IF;
        END $$;
        """
    )

    # The current database is empty for raw_materials, so make the new
    # canonical field required after adding it.
    _sql(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM raw_materials
                WHERE code IS NULL
            ) THEN
                ALTER TABLE raw_materials
                ALTER COLUMN code SET NOT NULL;
            END IF;
        END $$;
        """
    )

    # ------------------------------------------------------------------
    # 3. Scrap types
    # ------------------------------------------------------------------

    # stock was part of the old ORM/migration but is not part of the
    # approved canonical model. Remove it only when there is no data.
    _sql(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'scrap_types'
                  AND column_name = 'stock'
            ) THEN
                IF NOT EXISTS (SELECT 1 FROM scrap_types LIMIT 1) THEN
                    ALTER TABLE scrap_types DROP COLUMN stock;
                ELSE
                    RAISE EXCEPTION
                        'scrap_types.stock exists and scrap_types contains data';
                END IF;
            END IF;
        END $$;
        """
    )

    _sql(
        """
        ALTER TABLE scrap_types
        ADD COLUMN IF NOT EXISTS code VARCHAR(32)
        """
    )

    _sql(
        """
        ALTER TABLE scrap_types
        ADD COLUMN IF NOT EXISTS active BOOLEAN
        """
    )

    _sql(
        """
        UPDATE scrap_types
        SET active = TRUE
        WHERE active IS NULL
        """
    )

    _sql(
        """
        ALTER TABLE scrap_types
        ALTER COLUMN active SET DEFAULT TRUE
        """
    )

    _sql(
        """
        ALTER TABLE scrap_types
        ALTER COLUMN active SET NOT NULL
        """
    )

    _sql(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND indexname = 'ix_scrap_types_code'
            ) THEN
                CREATE UNIQUE INDEX ix_scrap_types_code
                ON scrap_types (code);
            END IF;
        END $$;
        """
    )

    _sql(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND indexname = 'ix_scrap_types_name'
            ) THEN
                CREATE UNIQUE INDEX ix_scrap_types_name
                ON scrap_types (name);
            END IF;
        END $$;
        """
    )

    # ------------------------------------------------------------------
    # 4. Scrap entries
    # ------------------------------------------------------------------

    _sql(
        """
        ALTER TABLE scrap_entries
        ADD COLUMN IF NOT EXISTS product_id VARCHAR(36)
        """
    )

    _sql(
        """
        ALTER TABLE scrap_entries
        ADD COLUMN IF NOT EXISTS remarks TEXT
        """
    )

    _sql(
        """
        UPDATE scrap_entries
        SET remarks = ''
        WHERE remarks IS NULL
        """
    )

    _sql(
        """
        ALTER TABLE scrap_entries
        ALTER COLUMN remarks SET DEFAULT ''
        """
    )

    _sql(
        """
        ALTER TABLE scrap_entries
        ALTER COLUMN remarks SET NOT NULL
        """
    )

    _sql(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'scrap_entries_product_id_fkey'
            ) THEN
                ALTER TABLE scrap_entries
                ADD CONSTRAINT scrap_entries_product_id_fkey
                FOREIGN KEY (product_id)
                REFERENCES products(id);
            END IF;
        END $$;
        """
    )

    _sql(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM scrap_entries
                WHERE product_id IS NULL
            ) THEN
                ALTER TABLE scrap_entries
                ALTER COLUMN product_id SET NOT NULL;
            END IF;
        END $$;
        """
    )

    # ------------------------------------------------------------------
    # 5. Delivery notes / lines
    # ------------------------------------------------------------------

    _sql(
        """
        ALTER TABLE delivery_notes
        ADD COLUMN IF NOT EXISTS so_no VARCHAR(32)
        """
    )

    _sql(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM delivery_notes
                WHERE so_no IS NULL
            ) THEN
                ALTER TABLE delivery_notes
                ALTER COLUMN so_no SET NOT NULL;
            END IF;
        END $$;
        """
    )

    _sql(
        """
        ALTER TABLE delivery_lines
        ADD COLUMN IF NOT EXISTS unit VARCHAR(16)
        """
    )

    _sql(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM delivery_lines
                WHERE unit IS NULL
            ) THEN
                ALTER TABLE delivery_lines
                ALTER COLUMN unit SET NOT NULL;
            END IF;
        END $$;
        """
    )

    # ------------------------------------------------------------------
    # 6. Dispatch uniqueness
    # ------------------------------------------------------------------

    _sql(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND indexname = 'uq_dispatch_delivery'
            )
            AND NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'uq_dispatch_delivery'
            ) THEN
                CREATE UNIQUE INDEX uq_dispatch_delivery
                ON dispatches (delivery_id);
            END IF;
        END $$;
        """
    )

    # ------------------------------------------------------------------
    # 7. Purchase order enum
    # ------------------------------------------------------------------

    _sql(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_type
                WHERE typname = 'purchaseorderstatus'
            ) THEN
                CREATE TYPE purchaseorderstatus AS ENUM (
                    'draft',
                    'sent',
                    'partially_received',
                    'received'
                );
            END IF;
        END $$;
        """
    )

    # ------------------------------------------------------------------
    # 8. Supplier products
    # ------------------------------------------------------------------

    _sql(
        """
        CREATE TABLE IF NOT EXISTS supplier_products (
            id VARCHAR(36) NOT NULL,
            supplier_id VARCHAR(36) NOT NULL,
            product_id VARCHAR(36) NOT NULL,
            supplier_code VARCHAR(64) NOT NULL,
            purchase_rate FLOAT NOT NULL,
            minimum_order_qty FLOAT NOT NULL,
            lead_time_days INTEGER NOT NULL,
            PRIMARY KEY (id),
            FOREIGN KEY (supplier_id) REFERENCES parties(id),
            FOREIGN KEY (product_id) REFERENCES raw_materials(id)
        )
        """
    )

    _sql(
        """
        CREATE INDEX IF NOT EXISTS ix_supplier_products_supplier_id
        ON supplier_products (supplier_id)
        """
    )

    _sql(
        """
        CREATE INDEX IF NOT EXISTS ix_supplier_products_product_id
        ON supplier_products (product_id)
        """
    )

    # ------------------------------------------------------------------
    # 9. Plants
    # ------------------------------------------------------------------

    _sql(
        """
        CREATE TABLE IF NOT EXISTS plants (
            id VARCHAR(36) NOT NULL,
            code VARCHAR(32) NOT NULL,
            name VARCHAR(160) NOT NULL,
            location VARCHAR(160) NOT NULL,
            active BOOLEAN NOT NULL,
            PRIMARY KEY (id),
            UNIQUE (name)
        )
        """
    )

    _sql(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ix_plants_code
        ON plants (code)
        """
    )

    # ------------------------------------------------------------------
    # 10. Warehouses
    # ------------------------------------------------------------------

    _sql(
        """
        CREATE TABLE IF NOT EXISTS warehouses (
            id VARCHAR(36) NOT NULL,
            code VARCHAR(32) NOT NULL,
            name VARCHAR(160) NOT NULL,
            plant_id VARCHAR(36) NOT NULL,
            active BOOLEAN NOT NULL,
            PRIMARY KEY (id),
            FOREIGN KEY (plant_id) REFERENCES plants(id)
        )
        """
    )

    _sql(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ix_warehouses_code
        ON warehouses (code)
        """
    )

    _sql(
        """
        CREATE INDEX IF NOT EXISTS ix_warehouses_plant_id
        ON warehouses (plant_id)
        """
    )

    # ------------------------------------------------------------------
    # 11. Purchase orders
    # ------------------------------------------------------------------

    _sql(
        """
        CREATE TABLE IF NOT EXISTS purchase_orders (
            id VARCHAR(36) NOT NULL,
            po_no VARCHAR(32) NOT NULL,
            po_date DATE NOT NULL,
            expected_date DATE,
            supplier_id VARCHAR(36) NOT NULL,
            supplier_name VARCHAR(160) NOT NULL,
            warehouse_id VARCHAR(36),
            notes TEXT NOT NULL,
            status purchaseorderstatus NOT NULL,
            sub_total FLOAT NOT NULL,
            gst_total FLOAT NOT NULL,
            grand_total FLOAT NOT NULL,
            created_by VARCHAR(64) NOT NULL,
            PRIMARY KEY (id),
            FOREIGN KEY (supplier_id) REFERENCES parties(id),
            FOREIGN KEY (warehouse_id) REFERENCES warehouses(id)
        )
        """
    )

    _sql(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ix_purchase_orders_po_no
        ON purchase_orders (po_no)
        """
    )

    _sql(
        """
        CREATE INDEX IF NOT EXISTS ix_purchase_orders_po_date
        ON purchase_orders (po_date)
        """
    )

    # ------------------------------------------------------------------
    # 12. Purchase order lines
    # ------------------------------------------------------------------

    _sql(
        """
        CREATE TABLE IF NOT EXISTS purchase_order_lines (
            id SERIAL NOT NULL,
            purchase_order_id VARCHAR(36) NOT NULL,
            material_id VARCHAR(36),
            material_name VARCHAR(160) NOT NULL,
            quantity FLOAT NOT NULL,
            rate FLOAT NOT NULL,
            gst_rate FLOAT NOT NULL,
            received_quantity FLOAT NOT NULL,
            tax FLOAT NOT NULL,
            total FLOAT NOT NULL,
            PRIMARY KEY (id),
            FOREIGN KEY (purchase_order_id)
                REFERENCES purchase_orders(id)
                ON DELETE CASCADE,
            FOREIGN KEY (material_id)
                REFERENCES raw_materials(id)
        )
        """
    )

    # ------------------------------------------------------------------
    # 13. GRNs
    # ------------------------------------------------------------------

    _sql(
        """
        CREATE TABLE IF NOT EXISTS grns (
            id VARCHAR(36) NOT NULL,
            grn_no VARCHAR(32) NOT NULL,
            grn_date DATE NOT NULL,
            purchase_order_id VARCHAR(36) NOT NULL,
            po_no VARCHAR(32) NOT NULL,
            warehouse_id VARCHAR(36) NOT NULL,
            PRIMARY KEY (id),
            FOREIGN KEY (purchase_order_id)
                REFERENCES purchase_orders(id),
            FOREIGN KEY (warehouse_id)
                REFERENCES warehouses(id)
        )
        """
    )

    _sql(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ix_grns_grn_no
        ON grns (grn_no)
        """
    )

    _sql(
        """
        CREATE INDEX IF NOT EXISTS ix_grns_grn_date
        ON grns (grn_date)
        """
    )

    # ------------------------------------------------------------------
    # 14. GRN lines
    # ------------------------------------------------------------------

    _sql(
        """
        CREATE TABLE IF NOT EXISTS grn_lines (
            id SERIAL NOT NULL,
            grn_id VARCHAR(36) NOT NULL,
            material_id VARCHAR(36) NOT NULL,
            material_name VARCHAR(160) NOT NULL,
            quantity FLOAT NOT NULL,
            batch_no VARCHAR(64) NOT NULL,
            PRIMARY KEY (id),
            FOREIGN KEY (grn_id)
                REFERENCES grns(id)
                ON DELETE CASCADE,
            FOREIGN KEY (material_id)
                REFERENCES raw_materials(id)
        )
        """
    )

    # ------------------------------------------------------------------
    # 15. Customer POs
    # ------------------------------------------------------------------

    _sql(
        """
        CREATE TABLE IF NOT EXISTS customer_pos (
            id VARCHAR(36) NOT NULL,
            po_no VARCHAR(64) NOT NULL,
            po_date DATE NOT NULL,
            customer_id VARCHAR(36) NOT NULL,
            customer_name VARCHAR(160) NOT NULL,
            delivery_date DATE,
            PRIMARY KEY (id),
            FOREIGN KEY (customer_id)
                REFERENCES parties(id)
        )
        """
    )

    _sql(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ix_customer_pos_po_no
        ON customer_pos (po_no)
        """
    )

    _sql(
        """
        CREATE INDEX IF NOT EXISTS ix_customer_pos_customer_id
        ON customer_pos (customer_id)
        """
    )

    # ------------------------------------------------------------------
    # 16. Customer PO lines
    # ------------------------------------------------------------------

    _sql(
        """
        CREATE TABLE IF NOT EXISTS customer_po_lines (
            id SERIAL NOT NULL,
            customer_po_id VARCHAR(36) NOT NULL,
            product_id VARCHAR(36),
            product_name VARCHAR(160) NOT NULL,
            quantity FLOAT NOT NULL,
            rate FLOAT,
            PRIMARY KEY (id),
            FOREIGN KEY (customer_po_id)
                REFERENCES customer_pos(id)
                ON DELETE CASCADE,
            FOREIGN KEY (product_id)
                REFERENCES products(id)
        )
        """
    )


def downgrade() -> None:
    # Intentionally non-destructive.
    #
    # This revision reconciles an already-live database and establishes the
    # procurement/customer-PO baseline. Dropping these structures during a
    # downgrade could destroy application data.
    pass
