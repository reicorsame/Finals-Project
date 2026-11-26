"""Small unit tests for models.py. Run:  python -m unittest -v"""
import unittest

from models import (CardPayment, Customer, Drink, GCashPayment, MenuItem, Order, OrderLine,
                    PaymentDeclined, PaymentMethod, Pastry, Breakfast, make_item,
                    ProductChecker, ProductCodeGenerator, ProductRule, DuplicateNameRule, NameRule)


class Abstraction(unittest.TestCase):
    def test_abstract_classes_cannot_be_created(self):
        with self.assertRaises(TypeError):
            MenuItem("x", 1)
        with self.assertRaises(TypeError):
            PaymentMethod()


class InheritanceAndPolymorphism(unittest.TestCase):
    def test_factory_returns_right_subclass(self):
        self.assertIsInstance(make_item("coffee", "Latte", 180), Drink)
        self.assertIsInstance(make_item("bakery", "Croissant", 145), Pastry)
        self.assertIsInstance(make_item("breakfast", "Brioche", 290), Breakfast)

    def test_prep_time_differs_per_class(self):
        items = [make_item(c, "x", 1) for c in ("coffee", "bakery", "breakfast")]
        self.assertEqual([i.prep_minutes for i in items], [4, 2, 12])
        self.assertEqual(items[2].prep_label(), "Cooked fresh, about 12 min")

    def test_payments_are_interchangeable(self):
        for pay in (GCashPayment("0917 123 4567"), CardPayment("4242 4242 4242 4242", "12/99", "123", "Ana")):
            self.assertIsNone(pay.check())
            self.assertTrue(pay.pay(100))

    def test_declines(self):
        with self.assertRaises(PaymentDeclined):
            GCashPayment("09000000000").pay(100)
        with self.assertRaises(PaymentDeclined):
            CardPayment("4000 0000 0000 0002", "12/99", "123", "Ana").pay(100)


class Encapsulation(unittest.TestCase):
    def test_negative_price_blocked(self):
        with self.assertRaises(ValueError):
            Drink("Latte", -1)

    def test_price_only_through_methods(self):
        item = Drink("Latte", 180)
        item.set_price(190)
        self.assertEqual(item.get_price(), 190.0)
        self.assertFalse(hasattr(item, "price"))

    def test_private_payment_data(self):
        self.assertEqual(GCashPayment("+63 917 123 4567").masked, "0917***4567")
        card = CardPayment("4242 4242 4242 4242", "12/99", "123", "Ana")
        self.assertEqual(card.label, "Card (**** 4242)")
        self.assertFalse(hasattr(card, "number") or hasattr(card, "cvc"))

    def test_card_validation(self):
        self.assertIn("valid card number", CardPayment("4242 4242 4242 4241", "12/99", "123", "A").check())
        self.assertIn("expired", CardPayment("4242 4242 4242 4242", "01/20", "123", "A").check())
        self.assertIn("security code", CardPayment("4242 4242 4242 4242", "12/99", "1", "A").check())


class Orders(unittest.TestCase):
    def test_order_total_and_label(self):
        lines = [OrderLine(1, "Latte", 180, 2), OrderLine(4, "Croissant", 145, 1)]
        order = Order(Customer("Ana", "0917"), lines, GCashPayment("09171234567"), "GCASH-1")
        self.assertEqual(order.total, 505.0)
        self.assertEqual(order.payment_label, "GCash (0917***4567)")
        self.assertTrue(order.order_number.startswith("CC-"))

    def test_empty_order_and_bad_line_rejected(self):
        with self.assertRaises(ValueError):
            Order(Customer("Ana", "0917"), [], GCashPayment("09171234567"), "x")
        with self.assertRaises(ValueError):
            OrderLine(1, "Latte", 180, 0)


class ProductChecks(unittest.TestCase):
    latte = staticmethod(lambda: make_item("coffee", "House Latte", 180, "Espresso with smooth steamed milk.", 11111))

    def test_rule_is_abstract_and_rules_are_polymorphic(self):
        with self.assertRaises(TypeError):
            ProductRule()
        rules = ProductChecker().rules
        self.assertTrue(all(isinstance(r, ProductRule) for r in rules))
        self.assertTrue(len({type(r) for r in rules}) == len(rules))

    def test_new_product_passes(self):
        new = make_item("bakery", "Cheese Roll", 90, "Soft roll filled with melted cheese.")
        self.assertEqual(ProductChecker().validate(new, [self.latte()]), [])

    def test_duplicate_name_blocked_even_with_other_case_and_spaces(self):
        dup = make_item("coffee", "  house   LATTE ", 99, "A totally different description here.")
        errors = ProductChecker().validate(dup, [self.latte()])
        self.assertEqual(len(errors), 1)
        self.assertIn("already exists", errors[0])

    def test_duplicate_description_blocked(self):
        dup = make_item("coffee", "Flat White", 150, "espresso with smooth steamed milk")
        errors = ProductChecker().validate(dup, [self.latte()])
        self.assertEqual(len(errors), 1)
        self.assertIn("same description", errors[0])

    def test_empty_and_short_fields_blocked(self):
        self.assertTrue(ProductChecker().validate(make_item("coffee", "x", 1, "short"), []))
        self.assertIn("name is required", NameRule().check(make_item("coffee", "  ", 1, "long enough text"), []))

    def test_find_duplicates_in_saved_products(self):
        a = self.latte()
        b = make_item("coffee", "House Latte", 180, "Another description entirely.", 22222)
        self.assertEqual(len(ProductChecker().find_duplicates([a, b])), 1)
        self.assertEqual(ProductChecker().find_duplicates([a]), [])

    def test_codes_are_unique_five_digits(self):
        gen = ProductCodeGenerator([10000, 10001])
        codes = [gen.next_code() for _ in range(500)]
        self.assertEqual(len(set(codes)), 500)
        self.assertTrue(all(10000 <= c <= 99999 for c in codes))
        self.assertNotIn(10000, codes)
        self.assertFalse(hasattr(gen, "used") or hasattr(gen, "__used"))


if __name__ == "__main__":
    unittest.main()
