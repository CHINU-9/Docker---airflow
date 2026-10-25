# Synthetic Multi-Source Data Engineering Practice Dataset

**All data is synthetic and fictional.** It is not copied from Salesforce, SFCC, NetSuite, CyberSource, or any live customer system. Emails use `example.test`; identifiers and amounts are illustrative.

## Contents
- `csv/`: CSV files for Excel, SQL ingestion, and batch-processing practice.
- `json/`: JSON arrays with raw-record-like structures. Some nested vendor fields are flattened for CSV compatibility.
- `schemas/`: schema notes with fields, example values, nullability, and row counts.
- `manifest.json`: dataset metadata and row counts.

## Datasets
| File base name | System | Meaning |
|---|---|---|
| `salesforce_crm_accounts` | Salesforce CRM | Account/company records |
| `salesforce_crm_contacts` | Salesforce CRM | Contacts linked to accounts by `AccountId` |
| `salesforce_crm_leads` | Salesforce CRM | Prospects and lead status |
| `salesforce_crm_opportunities` | Salesforce CRM | Sales opportunities linked to accounts |
| `sfcc_customers` | SFCC | Shopper/customer profile references |
| `sfcc_products` | SFCC | Product catalog and illustrative inventory |
| `sfcc_orders` | SFCC | Order headers linked to customer numbers |
| `sfcc_order_lines` | SFCC | Product rows linked to order headers |
| `netsuite_transactions` | NetSuite ERP | Invoice-like transaction headers; `externalId` links to SFCC order numbers |
| `netsuite_transaction_lines` | NetSuite ERP | Transaction line records |
| `netsuite_accounting_lines` | NetSuite ERP | Simplified accounting-line examples |
| `cybersource_payments` | CyberSource | Payment operations and processor response examples; merchant reference links to SFCC order number |

## Expected relationships
- CRM Contact `AccountId` -> CRM Account `Id`.
- CRM Opportunity `AccountId` -> CRM Account `Id`.
- SFCC Order `customerNo` -> SFCC Customer `customerNo`.
- SFCC Order Line `orderNo` -> SFCC Order `orderNo`.
- SFCC Order Line `productId` -> SFCC Product `productId`.
- NetSuite transaction `externalId` -> SFCC Order `orderNo` (some broken keys are intentional).
- NetSuite transaction line `transactionId` -> NetSuite transaction `id`.
- CyberSource `clientReferenceInformation.code` -> SFCC Order `orderNo` (some broken keys are intentional).

## Deliberate data-quality issues
Includes missing values, duplicate contact/payment records, broken foreign keys, invalid product price and order-line quantity, unexpected category/status values, and order/payment amount mismatches. Use these for profiling, validation, quarantine, and data-quality reports.

## Modeling notes
- This is a teaching dataset, not an exact mirror of any vendor's complete API schema.
- Real Salesforce fields depend on org metadata; SFCC shapes depend on SCAPI, OCAPI, or export format; NetSuite fields depend on the account's Records Catalog; CyberSource payloads vary by operation and processor.
- CyberSource fields with dotted names are flattened for practice; actual API responses commonly nest them.
- A transaction header can join to multiple lines. Aggregate at the correct grain to avoid double-counting.
- No real card numbers, credentials, secrets, or personal data are included.

## Suggested exercises
1. Count rows and profile null values.
2. Find duplicate CRM contacts and payment records.
3. Validate foreign keys in the relationship list.
4. Find negative prices and quantities.
5. Compare SFCC order totals to summed line amounts.
6. Compare payment amounts to linked order totals.
7. Build clean Silver tables and quarantine invalid rows.
8. Create Gold models for orders, payments, customers, and revenue.
9. Add dbt tests for unique keys, not-null fields, accepted values, and relationships.
10. Orchestrate the workflow with Airflow.

## Row counts
Main entities generally contain 1,000 rows. Detail tables contain 2,000 rows because there are two lines per order. CRM contacts and CyberSource payments each contain one extra row from a deliberate duplicate.
