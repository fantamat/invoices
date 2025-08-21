from pydantic import BaseModel, Field
from enum import Enum


class Currency(str, Enum):
    CZK = "CZK"
    EUR = "EUR"
    USD = "USD"
    OTHER = "unknown"


class Address(BaseModel):
    street: str = Field(description="Street address (ulice a číslo)")
    city: str = Field(description="City/town (město/obec)")
    postalcode: str = Field(description="Postal code (PSČ), e.g., '54932'")
    state: str = Field(description="State, province or region if present (e.g., 'California', 'Bayern')")
    country: str = Field(description="Country name")


class OwnCompanyName(str, Enum):
    DEYMED = "Deymed"
    ALIEN = "Alien"
    NONE = "None"

class InvoiceType(str, Enum):
    RECEIVED = "received" # FP
    ISSUED = "issued" # FV
    RECEIPT_RECEIVED = "receipt_received" # UP
    UNKNOWN = "unknown" # Unknown type, used for invoices that do not match any of the above types


class PaymentMethod(str, Enum):
    BANK_TRANSFER = "bank_transfer"
    CARD = "card"
    CASH = "cash"
    COD = "cod"
    CREDIT = "credit"
    ADVANCE = "advance"
    VOUCHER = "voucher"
    PAYPAL = "paypal"
    OFFSET = "offset"
    DIRECT_DEBIT = "direct_debit"
    UNKNOWN = "unknown"


class OwnCompanyInfo(BaseModel):
    name: OwnCompanyName = Field(description="Own company short name")
    company_name: str = Field(description="Our company legal name")
    address: Address = Field(description="Our company address block")
    identification_number: str = Field(description="Company IČO (CZ company registration number)")
    tax_number: str = Field(description="Company DIČ/VAT number (uppercase, keep country prefix if printed)")
    phone: str = Field(description="Company phone number")
    email: str = Field(description="Company email")


class CounterpartyInfo(BaseModel):
    company_name: str = Field(description="Counterparty legal name as printed (supplier/buyer). Do NOT swap with own company")
    address: Address = Field(description="Counterparty address block")
    identification_number: str = Field(description="Counterparty IČO")
    tax_number: str = Field(description="Counterparty DIČ/VAT number")
    phone: str = Field(description="Counterparty phone")
    email: str = Field(description="Counterparty email")


class ShippingInfo(BaseModel):
    address: Address = Field(description="Shipping/delivery address (place of delivery)", default=None)
    phone: str = Field(description="Shipping contact phone", default="")
    email: str = Field(description="Shipping contact email", default="")


class BankingInfo(BaseModel):
    account_number: str = Field(description="Bank account number. This is usually a 10-digit number in the format 1234567890 before the slash or 123456789/0800")
    bank_code: str = Field(description="Bank code. Usually a 4-digit code after the slash identifying the bank in the country, e.g., 0800 for Česká spořitelna")
    constant_symbol: str = Field(description="Constant symbol (KS)", default="")
    variable_symbol: str = Field(description="Variable symbol (VS; Variabilní symbol)", default="")
    specific_symbol: str = Field(description="Specific symbol (SS; Specifický symbol)", default="")
    iban: str = Field(description="International Bank Account Number (IBAN); (uppercase, no spaces). Prefer the exact printed sequence without spaces", default="")
    bic: str = Field(description="Bank Identifier Code (BIC/SWIFT)", default="")


class InvoiceLineItem(BaseModel):
    name: str = Field(description="Exact item name/description as printed on the invoice. Do not translate or modify")
    mfr_part_no: str = Field(description="Manufacturer part number (P/N) if explicitly printed, otherwise empty", default="")
    ean: str = Field(description="EAN/GTIN barcode number if explicitly printed, otherwise empty", default="")
    quantity: float = Field(description="Quantity exactly as printed on the invoice (number only, no text)")
    unit: str = Field(description="Unit of measure exactly as printed (e.g., 'ks', 'pcs', 'kg'). If not printed, use 'ks' as default", default="ks")
    unit_price: float = Field(description="Unit price for this line. Use the exact value printed on the document. If both net (bez DPH) and gross (s DPH) are shown, store the NET (without VAT). If only a gross price is printed (e.g., receipts), use that value as-is")
    ext_price: float = Field(description="Line total price as printed on the invoice. Prefer the value shown in the document. Only calculate (quantity * unit_price) if no line total is explicitly printed")
    tax_class_id: float = Field(description="VAT rate (%) for this line, exactly as shown. If not specified and cannot be inferred from totals, set null")
    discount_percent: float = Field(description="Line discount percent as printed. Use 0 if no discount is shown", default=0.0)
    total_with_vat: float = Field(description="Line total including VAT. Use the exact value printed on the document if available. Only calculate if no total with VAT is printed")


class Invoice(BaseModel):
    type: InvoiceType = Field(description="Invoice document type. Heuristics: receipts usually lack due date/bank; 'issued' vs 'received' by header roles and CZ terms (Dodavatel/Odběratel)")

    internal_invoice_number: str = Field(description="Internal invoice number. Invoice  Required for all invoice types. This could be a purchase order number or an external order number, e.g., DNO25052613. Purchase order ID starts with 'DNO' and is followed by the date (YYMMDD) and a sequence number (two digits). This ID may be hand written on the invoice in its top corner", default="")
    external_invoice_number: str = Field(description="External invoice number. Invoice number assigned by the counterparty (Číslo faktury/Invoice No.)", default="")

    delivery_note_number: str = Field(description="Delivery note number (Číslo dodacího listu)", default="")

    # Additional identifiers
    # Dates
    issue_date: str = Field(description="Invoice issue date. Normalize any of these formats to YYYY-MM-DD")
    due_date: str = Field(description="Due date (Splatnost). Normalize to YYYY-MM-DD. Receipts typically have none", default="")

    taxable_supply_date: str = Field(description="Taxable supply date (DUZP/Datum uskutečnění zdanitelného plnění). Normalize to YYYY-MM-DD if present", default="")
    deduction_date: str = Field(description="VAT deduction date. Normalize to YYYY-MM-DD if present", default="")
    
    # Payment information
    payment_method: PaymentMethod = Field(description="Payment method derived from the document")
    banking_info: BankingInfo = Field(description="Bank/payment block")
    
    # Company information
    own_company_info: OwnCompanyInfo = Field(description="Our company details (do not swap with counterparty). It should be only DEYMED Diagnostic or ALIEN technology company")
    counterparty_info: CounterpartyInfo = Field(description="Counterparty details (do not swap with own_company_info).")
    shipping_info: ShippingInfo = Field(description="Shipping/delivery information", default=None)
    
    # Invoice amounts
    amount_discount: float = Field(description="Total discount amount in currency", default=0.0)
    amount_without_discount: float = Field(description="Subtotal before discount", default=0.0)
    
    amount_without_rounding: float = Field(description="Total price after discount before rounding", default=0.0)
    amount_rounding: float = Field(description="Rounding adjustment (may be positive or negative)", default=0.0)
    amount_total: float = Field(description="Grand total for the entire invoice/receipt including rounding (sum of lines with VAT, plus/minus rounding)", default=0.0)

    currency_id: Currency = Field(description="Document currency code (CZK/EUR/USD/unknown)")
    vat_currency_id: Currency = Field(description="VAT currency if printed separately", default=None)
    
    # Additional information
    description: str = Field(description="Free-form notes, description of the transaction or incidental IDs (e.g., shipment tracking) that do not belong to structured ID fields", default="")

    place_of_issue: str = Field(description="Place/branch where the invoice was issued (Provozovna/Místo vystavení)", default="")

    # Line items
    lines: list[InvoiceLineItem] = Field(description="Invoice line items")



