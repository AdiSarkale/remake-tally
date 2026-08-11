# Mini Manufacturing Hub

Build a full-stack web application called "MiniTally ERP" inspired by Tally Prime but designed for a small manufacturing business.

The application should be modern, responsive, secure, and simple to use. Focus on clean UI rather than copying Tally's interface.

Technology:

- Frontend: React + TypeScript + Tailwind CSS

- Backend: FastAPI (Python)

- Database: PostgreSQL

- JWT Authentication

- REST API architecture

- Docker support

- Role Based Access (Admin, Accountant, Operator)

The application should have the following modules.

--------------------------------------------------

1. Authentication

--------------------------------------------------

- Login

- Logout

- Change Password

- JWT Authentication

- Password hashing

- User roles

--------------------------------------------------

2. Dashboard

--------------------------------------------------

Show summary cards:

- Today's Production

- Total Finished Goods

- Total Scrap

- Total Sales

- Pending Payments

- Inventory Value

Include:

- Production chart

- Sales chart

- Recent invoices

- Low stock alerts

--------------------------------------------------

3. Masters

--------------------------------------------------

Customers

Fields:

- Customer Name

- GST Number

- Mobile

- Email

- Address

Suppliers

Fields:

- Supplier Name

- GST

- Contact

- Address

Products

Fields:

- Product Code

- Product Name

- Category

- Unit

- Selling Price

- Cost Price

- HSN Code

- GST Percentage

- Minimum Stock

Raw Materials

- Material Name

- Unit

- Cost

- Current Stock

Scrap Types

- Scrap Name

- Unit

- Selling Rate

--------------------------------------------------

4. Inventory

--------------------------------------------------

Inventory management should support:

Stock In

Stock Out

Current Stock

Adjust Stock

Inventory History

Search

Filters

Stock valuation

Low stock warning

--------------------------------------------------

5. Production Module

--------------------------------------------------

Create production entry.

Fields:

Production Date

Product Produced

Quantity Produced

Machine

Operator

Shift

Remarks

Each production should consume raw materials.

Automatically reduce raw material stock.

Automatically increase finished goods stock.

--------------------------------------------------

6. Scrap Management

--------------------------------------------------

Record production scrap.

Fields:

Date

Product

Production Batch

Scrap Type

Quantity

Reason

Remarks

Dashboard should show:

Daily Scrap

Monthly Scrap

Scrap Percentage

Top Scrap Reasons

--------------------------------------------------

7. Sales Invoice

--------------------------------------------------

Professional invoice similar to Tally.

Invoice Number (Auto)

Invoice Date

Customer

Products

Quantity

Rate

Discount

GST

CGST

SGST

IGST

Subtotal

Grand Total

Payment Status

Generate PDF Invoice

Print Invoice

Download Invoice

Email Invoice

Invoice History

Search Invoice

--------------------------------------------------

8. Purchase Entry

--------------------------------------------------

Purchase invoices from suppliers.

Auto update inventory.

GST calculation.

Invoice history.

--------------------------------------------------

9. Payments

--------------------------------------------------

Customer Payments

Supplier Payments

Outstanding Bills

Partial Payments

Payment History

Cash Book

--------------------------------------------------

10. Reports

--------------------------------------------------

Sales Report

Purchase Report

Inventory Report

Production Report

Scrap Report

GST Report

Customer Ledger

Supplier Ledger

Profit Summary

Date filters

Export to Excel

Export to PDF

--------------------------------------------------

11. Settings

--------------------------------------------------

Company Details

Company Logo

GST Number

Invoice Prefix

Financial Year

Users

Roles

Backup Database

Restore Database

--------------------------------------------------

12. Database Design

--------------------------------------------------

Create proper relational tables for:

Users

Customers

Suppliers

Products

Raw Materials

Inventory

Production

Production Consumption

Scrap Entries

Invoices

Invoice Items

Purchases

Purchase Items

Payments

Audit Logs

--------------------------------------------------

13. UI Requirements

--------------------------------------------------

Use a modern ERP dashboard.

Sidebar Navigation

Top Navbar

Dark Mode

Light Mode

Search Everywhere

Responsive layout

Pagination

Sorting

Filtering

Confirmation dialogs

Toast notifications

Loading animations

--------------------------------------------------

14. Backend Features

--------------------------------------------------

FastAPI

SQLAlchemy

Alembic

JWT Authentication

Repository Pattern

Service Layer

Pydantic Schemas

Swagger Documentation

Error Handling

Validation

Logging

Pagination

Filtering

Search APIs

--------------------------------------------------

15. Future Ready

--------------------------------------------------

Design the project so future modules can be added:

Payroll

Barcode Scanner

QR Code

Warehouse

Multiple Branches

Multi Company

Expense Tracking

Manufacturing BOM

Purchase Orders

Sales Orders

Customer Portal

Supplier Portal

Analytics Dashboard

--------------------------------------------------

16. Important Business Logic

--------------------------------------------------

When production is created:

- Finished goods increase.

- Raw materials decrease.

When invoice is generated:

- Finished goods stock decreases.

When purchase is entered:

- Raw material stock increases.

When scrap is recorded:

- Scrap inventory increases.

- Scrap percentage is recalculated.

All inventory movements must be logged.

--------------------------------------------------

17. General Requirements

--------------------------------------------------

Create clean reusable components.

Use proper folder structure.

Write modular backend code.

Implement validation.

Prevent duplicate invoices.

Generate sequential invoice numbers.

Keep the UI simple, fast and beginner friendly.

The project should resemble a lightweight version of Tally suitable for small manufacturing businesses, focusing mainly on invoicing, inventory, production tracking, and scrap management rather than full accounting.

This project was built with [Lovable](https://lovable.dev).

**Live app**: https://remake-tally.lovable.app

## Build with Lovable

Continue developing this project in the [Lovable editor](https://lovable.dev/projects/a40a96ea-54b7-48a7-b598-babd2375344e).

- **Ship faster**: describe what you want to build and Lovable handles the code.
- **Stay in sync**: every change made in Lovable is committed straight to this repository.
- **Full ownership**: this code is yours. Push to `main` on GitHub and your changes sync back into Lovable, ready for your next prompt.

## Development

Prefer working locally? You need Node.js and npm — [install with nvm](https://github.com/nvm-sh/nvm#installing-and-updating).

```sh
git clone <this-repository-url>
cd <repository-name>
npm i
npm run dev
```
