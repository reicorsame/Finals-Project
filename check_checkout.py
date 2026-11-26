"""End-to-end checkout checks on a throw-away copy of the database.  Run:  python check_checkout.py"""
import io, os, shutil, sqlite3, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(tempfile.mkdtemp(), "test.db")
shutil.copy(os.path.join(HERE, "shop.db"), DB)
os.environ["CRIMSON_DB"] = DB
sys.path.insert(0, HERE)
import app as A
A.UPLOAD_FOLDER = tempfile.mkdtemp()      # uploaded test images go to a temp folder, not static/img
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32

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
# ---- cart auto-update (no Update button) ----
cc = shopper()
r = cc.post("/cart/update", data={"quantity_1": "5", "quantity_4": "0"}, headers={"X-Requested-With": "fetch"})
data = r.get_json()
check("cart update returns JSON totals", data["count"] == 5 and data["total"] == 900.0 and list(data["lines"]) == ["1"], data)
cart_page = cc.get("/cart").get_data(as_text=True)
check("cart page has no Update button outside <noscript>", "Update cart" not in cart_page.replace("<noscript><button class=\"button secondary\">Update cart</button></noscript>", ""))
check("bad quantity text is ignored", cc.post("/cart/update", data={"quantity_1": "abc"}, headers={"X-Requested-With": "fetch"}).get_json()["count"] == 5)

# ---- admin: unique 5-digit codes and duplicate checks ----
codes = [r[0] for r in q("select code from products")]
check("every product has a unique 5-digit code", len(codes) == len(set(codes)) and all(c and 10000 <= c <= 99999 for c in codes), codes)
a = A.app.test_client(); a.post("/admin/login", data={"username": "admin", "password": "admin123"})
def add(**over):
    form = {"name": "Cheese Roll", "description": "Soft roll filled with melted cheese.", "price": "90", "category": "bakery"}
    form.update(over); form["image"] = (io.BytesIO(PNG), "roll.png")
    return a.post("/admin/products/add", data=form, content_type="multipart/form-data", follow_redirects=True).get_data(as_text=True)
n = q("select count(*) from products")[0][0]
page = add()
check("new product is added", q("select count(*) from products")[0][0] == n + 1 and "Cheese Roll" in page)
new_code = q("select code from products where name='Cheese Roll'")[0][0]
check("new product gets a 5-digit code not used before", 10000 <= new_code <= 99999 and new_code not in codes and f"#{new_code}" in page)
check("same name is blocked", "already exists" in add(description="A different description for the same name.") and q("select count(*) from products")[0][0] == n + 1)
check("same name, other case/spaces, is blocked", "already exists" in add(name="  cheese   ROLL ", description="Another description text here.") and q("select count(*) from products")[0][0] == n + 1)
check("same description is blocked", "same description" in add(name="Ham Roll") and q("select count(*) from products")[0][0] == n + 1)
check("empty description is blocked", "Description is required" in add(name="Ham Roll", description=""))
check("negative price is blocked", "negative" in add(name="Ham Roll", description="Soft roll with sliced ham inside.", price="-5").lower())
check("price text is blocked", "Price must be" in add(name="Ham Roll", description="Soft roll with sliced ham inside.", price="abc"))
pid = q("select id from products where name='Cheese Roll'")[0][0]
other = q("select id from products where name='House Latte'")[0][0]
r = a.post(f"/admin/products/{pid}/edit", data={"name": "House Latte", "description": "Soft roll filled with melted cheese.", "price": "90", "category": "bakery", "availability": "1"}, follow_redirects=True)
check("editing into another product's name is blocked", "already exists" in r.get_data(as_text=True) and q(f"select name from products where id={pid}")[0][0] == "Cheese Roll")
r = a.post(f"/admin/products/{pid}/edit", data={"name": "Cheese Roll", "description": "Soft roll filled with melted cheese.", "price": "95", "category": "bakery", "availability": "1"}, follow_redirects=True)
check("saving a product without changing its name works", q(f"select price from products where id={pid}")[0][0] == 95.0 and q(f"select code from products where id={pid}")[0][0] == new_code)

# ---- old databases get codes added, duplicates are reported ----
old = sqlite3.connect(DB); old.execute("INSERT INTO products (name, description, price, image, category, availability, code) VALUES ('House Latte', 'Copy of the latte', 1, 'cafe-latte.jpg', 'coffee', 1, NULL)"); old.commit(); old.close()
A.setup_database()
check("missing code is filled in on start", q("select count(*) from products where code is null")[0][0] == 0)
check("dashboard warns about existing duplicates", "Duplicate products found" in a.get("/admin").get_data(as_text=True))
print("\nFAILURES:", fails)
sys.exit(1 if fails else 0)
