"""End-to-end checkout checks on a throw-away copy of the database.  Run:  python check_checkout.py"""
import os, shutil, sqlite3, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(tempfile.mkdtemp(), "test.db")
shutil.copy(os.path.join(HERE, "shop.db"), DB)
os.environ["CRIMSON_DB"] = DB
sys.path.insert(0, HERE)
import app as A

fails = 0
def check(name, ok, extra=""):
    global fails
    print(("PASS " if ok else "FAIL ") + name, "" if ok else extra)
    fails += 0 if ok else 1

def q(sql):
    con = sqlite3.connect(DB); rows = con.execute(sql).fetchall(); con.close(); return rows

def shopper():
    c = A.app.test_client(); c.post("/cart/add/1", data={"quantity": 2}); c.post("/cart/add/4"); return c

base = {"customer_name": "Jane", "contact_number": "0917 000 1111", "order_type": "Takeout", "table_number": "", "notes": "",
        "payment_method": "card", "card_name": "Jane Doe", "card_number": "4242 4242 4242 4242", "card_expiry": "12/99", "card_cvc": "123",
        "gcash_number": "0917 123 4567"}
n0 = q("select count(*) from orders")[0][0]

c = shopper()
for label, over, msg in [("bad card number", {"card_number": "4242 4242 4242 4241"}, "valid card number"),
                         ("expired card", {"card_expiry": "01/20"}, "expired"),
                         ("bad security code", {"card_cvc": "1"}, "security code"),
                         ("declined card", {"card_number": "4000 0000 0000 0002"}, "declined"),
                         ("missing name", {"customer_name": ""}, "name and contact"),
                         ("dine-in without table", {"order_type": "Dine-in"}, "table number"),
                         ("bad GCash number", {"payment_method": "gcash", "gcash_number": "123"}, "valid gcash")]:
    text = c.post("/checkout", data={**base, **over}).get_data(as_text=True).lower()
    check(label + " -> error shown", msg in text)
check("no order saved by any failure", q("select count(*) from orders")[0][0] == n0)
check("cart kept after failures", b"House Latte" in c.get("/cart").data)

r = c.post("/checkout", data=base)
check("valid card -> receipt", r.status_code == 302 and "/receipt/CC-" in r.headers["Location"])
page = c.get(r.headers["Location"]).get_data(as_text=True)
check("receipt shows card, reference, total", "Card (**** 4242)" in page and "CARD-" in page and "505.00" in page)
row = q("select payment_method, payment_status, total from orders order by id desc limit 1")[0]
check("order row saved correctly", row == ("Card (**** 4242)", "Paid", 505.0), row)
check("full card number never stored", b"4242424242424242" not in open(DB, "rb").read())

g = shopper()
r = g.post("/checkout", data={**base, "payment_method": "gcash"})
check("GCash -> approval page", r.headers["Location"].endswith("/gcash/pay"))
r = g.post("/gcash/pay", data={"action": "approve"})
check("GCash approve -> receipt", "/receipt/CC-" in r.headers["Location"])
g = shopper(); g.post("/checkout", data={**base, "payment_method": "gcash", "gcash_number": "09000000000"})
check("declined GCash number -> no order", "not enough wallet" in g.post("/gcash/pay", data={"action": "approve"}).get_data(as_text=True)
      and q("select count(*) from orders")[0][0] == n0 + 2)

for path in ("/", "/menu", "/product/1", "/product/6", "/cart", "/admin/login"):
    check(path + " loads", A.app.test_client().get(path).status_code == 200)
a = A.app.test_client(); a.post("/admin/login", data={"username": "admin", "password": "admin123"})
check("admin dashboard", a.get("/admin").status_code == 200)
print("\nFAILURES:", fails)
sys.exit(1 if fails else 0)
