from pydantic import BaseModel, Field
from enum import Enum


class Currency(str, Enum):
    CZK = "CZK"
    EUR = "EUR"
    USD = "USD"
    OTHER = "unknown"


class Address(BaseModel):
    street: str = Field(description="Street address")
    city: str = Field(description="City")
    postalcode: str = Field(description="Postal code")
    country: str = Field(description="Country")


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
    name: OwnCompanyName = Field(description="Company name")
    company_name: str = Field(description="Company name")
    address: Address = Field(description="Company address")
    identification_number: str = Field(description="Company identification number (IČO)")
    tax_number: str = Field(description="Company VAT number (DIČ)")
    phone: str = Field(description="Company phone number")
    email: str = Field(description="Company email")


class CounterpartyInfo(BaseModel):
    company_name: str = Field(description="Company name")
    address: Address = Field(description="Company address")
    identification_number: str = Field(description="Company identification number (IČO)")
    tax_number: str = Field(description="Company VAT number (DIČ)")
    phone: str = Field(description="Company phone number")
    email: str = Field(description="Company email")


class ShippingInfo(BaseModel):
    account_id: str = Field(description="Shipping account ID. For example company name.", default="")
    contact_id: str = Field(description="Shipping contact ID. Name of the person responsible for shipping.", default="")
    address: Address = Field(description="Shipping address", default=None)
    phone: str = Field(description="Shipping phone number", default="")
    email: str = Field(description="Shipping email", default="")


class BankingInfo(BaseModel):
    account_number: str = Field(description="Bank account number. This is usually a 10-digit number in the format 1234567890 before the slash or 123456789/0800")
    bank_code: str = Field(description="Bank code. Usually a 4-digit code after the slash identifying the bank in the country, e.g., 0800 for Česká spořitelna")
    constant_symbol: str = Field(description="Constant symbol", default="")
    variable_symbol: str = Field(description="Variable symbol", default="")
    specific_symbol: str = Field(description="Specific symbol", default="")
    iban: str = Field(description="International Bank Account Number (IBAN)", default="")
    bic: str = Field(description="Bank Identifier Code (BIC/SWIFT)", default="")


class InvoiceLineItem(BaseModel):
    name: str = Field(description="Name of the item")
    mfr_part_no: str = Field(description="Manufacturer part number", default="")
    ean: str = Field(description="EAN code", default="")
    quantity: float = Field(description="Quantity")
    unit: str = Field(description="Unit of measure", default="ks")
    unit_price: float = Field(description="Unit price without VAT")
    ext_price: float = Field(description="Total price without VAT")
    tax_class_id: float = Field(description="VAT rate in percentage")
    discount_percent: float = Field(description="Discount percentage", default=0.0)
    total_with_vat: float = Field(description="Total price with VAT")


class Invoice(BaseModel):
    type: InvoiceType = Field(description="Type of invoice")
    
    internal_invoice_number: str = Field(description="Internal invoice number. Invoice  Required for all invoice types. This could be a purchase order number or an external order number, e.g., DNO25052613. Purchase order ID starts with 'DNO' and is followed by the date (YYMMDD) and a sequence number (two digits). This ID may be hand written on the invoice in its top corner.", default="")
    external_invoice_number: str = Field(description="External invoice number. Invoice number assigned by the counterparty. Required for invoices received.", default="")

    delivery_note_number: str = Field(description="Delivery note number. Not required for the type receipt_received.", default="")

    # Additional identifiers
    # Dates
    issue_date: str = Field(description="Issue date")
    due_date: str = Field(description="Due date. Not required for the type receipt_received.", default="")

    taxable_supply_date: str = Field(description="Taxable supply date", default="")
    deduction_date: str = Field(description="VAT deduction date. Not required for the type receipt_received.", default="")
    
    # Payment information
    payment_method: PaymentMethod = Field(description="Payment method. Required for all invoice types.")
    banking_info: BankingInfo = Field(description="Banking information. Not required for the type receipt_received.")
    
    # Company information
    own_company_info: OwnCompanyInfo = Field(description="Own company information")
    counterparty_info: CounterpartyInfo = Field(description="Counterparty information")
    shipping_info: ShippingInfo = Field(description="Shipping information", default=None)
    
    # Invoice amounts
    amount_wo_rounding: float = Field(description="Total price before rounding")
    amount_rounding: float = Field(description="Rounding amount", default=0.0)
    amount: float = Field(description="Total amount to pay")
    currency_id: Currency = Field(description="Currency")
    vat_currency_id: Currency = Field(description="VAT currency", default=None)
    
    # Additional information
    description: str = Field(description="Description of the transaction", default="")

    # Line items
    lines: list[InvoiceLineItem] = Field(description="Invoice line items")



