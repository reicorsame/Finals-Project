"""
The four OOP principles are demonstrated in this file:

Abstraction   - MenuItem and PaymentMethod are abstract: they only say WHAT must exist.
Inheritance   - Drink, Pastry, Breakfast extend MenuItem; GCashPayment extends PaymentMethod.
Polymorphism  - every item answers prep_minutes in its own way; every payment answers pay().
Encapsulation - price and the GCash number are private and only reachable through methods.

The same ideas also protect the admin dashboard: ProductRule (abstract) and its subclasses
check new products for duplicate names/descriptions, and ProductCodeGenerator hands out unique
5-digit product codes.
"""
from abc import ABC, abstractmethod
from datetime import date, datetime
import random
import re
import uuid


# Menu items (Abstraction)
class MenuItem(ABC):
    def __init__(self, name, price, description="", code=None):
        self.name = name
        self.description = description
        self.code = code              # unique 5-digit product code (see ProductCodeGenerator)
        self.__price = 0
        self.set_price(price)

    # Private price, read and changed only through methods (Encapsulation)
    def get_price(self):
        return self.__price

    def set_price(self, value):
        if float(value) < 0:
            raise ValueError("Price cannot be negative.")
        self.__price = float(value)

    # Abstract method (Abstraction)
    @property
    @abstractmethod
    def prep_minutes(self):
        """Every item type must say how long it takes to prepare."""

    def prep_label(self):
        return f"Ready in about {self.prep_minutes} min"


# Drink, Pastry, Breakfast (Inheritance)
class Drink(MenuItem):
    prep_minutes = 4


class Pastry(MenuItem):
    prep_minutes = 2


class Breakfast(MenuItem):
    prep_minutes = 12

    # Overrides MenuItem.prep_label (Polymorphism)
    def prep_label(self):
        return f"Cooked fresh, about {self.prep_minutes} min"


# Factory pattern: picks the right subclass for a category
def make_item(category, name, price, description="", code=None):
    kinds = {"coffee": Drink, "bakery": Pastry, "breakfast": Breakfast}
    return kinds.get(category, Pastry)(name, price, description, code)


# Unique 5-digit product codes (Encapsulation): the used codes are private to the generator
class ProductCodeGenerator:
    LOW, HIGH = 10000, 99999

    def __init__(self, used_codes=()):
        self.__used = {int(c) for c in used_codes if c is not None}     # private

    def next_code(self):
        if len(self.__used) > self.HIGH - self.LOW:
            raise RuntimeError("No 5-digit codes left.")
        while True:
            code = random.randint(self.LOW, self.HIGH)
            if code not in self.__used:
                self.__used.add(code)
                return code


# Product rules (Abstraction): each rule says what to check, subclasses decide how
def _same(text):
    """Compare text ignoring capital letters, extra spaces and end punctuation."""
    return re.sub(r"\s+", " ", (text or "").strip()).lower().rstrip(".!")


class ProductRule(ABC):
    @abstractmethod
    def check(self, item, others):
        """Return an error message if `item` breaks the rule, otherwise None."""


# Inheritance + Polymorphism: every rule below is a ProductRule with its own check()
class NameRule(ProductRule):
    def check(self, item, others):
        if not item.name.strip():
            return "Product name is required."
        if len(item.name.strip()) > 60:
            return "Product name must be 60 characters or fewer."
        return None


class DescriptionRule(ProductRule):
    def check(self, item, others):
        if len(item.description.strip()) < 10:
            return "Description is required (at least 10 characters)."
        return None


class DuplicateNameRule(ProductRule):
    def check(self, item, others):
        for other in others:
            if _same(other.name) == _same(item.name):
                return f"A product named \"{other.name}\" already exists (code {other.code})."
        return None


class DuplicateDescriptionRule(ProductRule):
    def check(self, item, others):
        for other in others:
            if _same(other.description) == _same(item.description):
                return f"\"{other.name}\" (code {other.code}) already uses the same description."
        return None


# Checker (Composition): holds a list of rules and treats them all the same way
class ProductChecker:
    def __init__(self, rules=None):
        self.rules = rules or [NameRule(), DescriptionRule(), DuplicateNameRule(), DuplicateDescriptionRule()]

    def validate(self, item, others):
        """Run every rule. Returns a list of error messages (empty = OK)."""
        errors = [rule.check(item, others) for rule in self.rules]
        return [e for e in errors if e]

    def find_duplicates(self, items):
        """Look through products already saved and describe any that repeat a name or description."""
        found = []
        for index, item in enumerate(items):
            for rule in (DuplicateNameRule(), DuplicateDescriptionRule()):
                message = rule.check(item, items[:index])
                if message:
                    found.append(f"\"{item.name.strip()}\" (code {item.code}): {message}")
        return found


# Payments
class PaymentDeclined(Exception):
    pass


# PaymentMethod (Abstraction)
class PaymentMethod(ABC):
    @abstractmethod
    def check(self):
        """Return an error message if the payment details are wrong, otherwise None."""

    @property
    @abstractmethod
    def label(self):
        """Short text saved on the order, e.g. 'GCash (0917***4567)'."""

    @abstractmethod
    def pay(self, amount):
        """Charge the amount. Returns a payment reference or raises PaymentDeclined."""


# GCashPayment (Inheritance + Polymorphism)
class GCashPayment(PaymentMethod):
    DECLINE_NUMBER = "09000000000"      # DEMO: this number is always declined

    def __init__(self, raw_number):
        digits = re.sub(r"[\s-]", "", raw_number or "")
        if digits.startswith("+63"):
            digits = "0" + digits[3:]
        elif digits.startswith("63") and len(digits) == 12:
            digits = "0" + digits[2:]
        self.__number = digits if re.fullmatch(r"09\d{9}", digits) else None   # private

    @property
    def number(self):
        return self.__number

    @property
    def masked(self):
        return self.__number[:4] + "***" + self.__number[-4:]

    @property
    def label(self):
        return "GCash (" + self.masked + ")"

    def check(self):
        if not self.__number:
            return "Please enter a valid GCash mobile number, for example 0917 123 4567."
        return None

    def pay(self, amount):
        if self.__number == self.DECLINE_NUMBER:
            raise PaymentDeclined("GCash payment failed: not enough wallet balance (demo test number).")
        return "GCASH-" + uuid.uuid4().hex[:10].upper()


# CardPayment (Inheritance + Polymorphism)
class CardPayment(PaymentMethod):
    DECLINE_CARD = "4000000000000002"      # DEMO: this card is always declined

    def __init__(self, number, expiry, cvc, holder=""):
        self.__number = re.sub(r"[\s-]", "", number or "")     
        self.__cvc = (cvc or "").strip()                       
        self.expiry = (expiry or "").strip()
        self.holder = (holder or "").strip()

    @property
    def last4(self):
        return self.__number[-4:]

    @property
    def label(self):
        return "Card (**** " + self.last4 + ")"

    def __luhn_ok(self):
        total = 0
        for i, ch in enumerate(reversed(self.__number)):
            digit = int(ch)
            if i % 2 == 1:
                digit = digit * 2 - 9 if digit > 4 else digit * 2
            total += digit
        return total % 10 == 0

    def check(self):
        if not self.holder:
            return "Please enter the name on the card."
        if not (self.__number.isdigit() and 13 <= len(self.__number) <= 19 and self.__luhn_ok()):
            return "Please enter a valid card number."
        match = re.fullmatch(r"(\d{2})\s*/\s*(\d{2})", self.expiry)
        if not match or not 1 <= int(match.group(1)) <= 12:
            return "Expiry date must look like MM/YY."
        today = date.today()
        if (2000 + int(match.group(2)), int(match.group(1))) < (today.year, today.month):
            return "This card has expired."
        if not re.fullmatch(r"\d{3,4}", self.__cvc):
            return "Please enter the 3 or 4 digit security code."
        return None

    def pay(self, amount):
        if self.__number == self.DECLINE_CARD:
            raise PaymentDeclined("Card declined by the bank (demo test card).")
        return "CARD-" + uuid.uuid4().hex[:10].upper()


# Orders (Encapsulation)
class OrderLine:
    """One product on an order. Keeps its own copy of the name and price."""

    def __init__(self, product_id, name, price, quantity):
        if int(quantity) < 1:
            raise ValueError("Quantity must be at least 1.")
        if float(price) < 0:
            raise ValueError("Price cannot be negative.")
        self.product_id = product_id
        self.name = name
        self.__price = float(price)          
        self.__quantity = int(quantity)      

    price = property(lambda self: self.__price)
    quantity = property(lambda self: self.__quantity)

    @property
    def subtotal(self):
        return round(self.__price * self.__quantity, 2)


class Customer:
    def __init__(self, name, contact_number, order_type="Takeout", table_number="", notes=""):
        self.name = name
        self.contact_number = contact_number
        self.order_type = order_type
        self.table_number = table_number
        self.notes = notes


class Order:
    """A paid order: it owns its lines (composition) and uses one payment method."""

    def __init__(self, customer, lines, payment, reference):
        if not lines:
            raise ValueError("An order needs at least one item.")
        self.order_number = "CC-" + uuid.uuid4().hex[:6].upper()
        self.created_at = datetime.now().isoformat(timespec="minutes")
        self.customer = customer             
        self.lines = list(lines)             
        self.payment = payment               
        self.reference = reference

    @property
    def total(self):
        return round(sum(line.subtotal for line in self.lines), 2)

    @property
    def payment_label(self):
        return self.payment.label
