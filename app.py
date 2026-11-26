from functools import wraps
from flask import Flask, abort, flash, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
import re
import sqlite3
from datetime import datetime
import os
import uuid
from werkzeug.utils import secure_filename
from models import (CardPayment, Customer, GCashPayment, Order, OrderLine, PaymentDeclined,
                    ProductChecker, ProductCodeGenerator, make_item)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "crimson-cafe-demo-key")
DATABASE = os.environ.get("CRIMSON_DB", os.path.join(BASE_DIR, "shop.db"))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "img")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5 MB

CATEGORIES = ["all", "coffee", "bakery", "breakfast"]
HERO_IMAGE = "croissant-board.jpg"


def get_db():
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db
def save_product_image(file):
    if not file or not file.filename:
        return None

    filename = secure_filename(file.filename)

    if "." not in filename:
        raise ValueError("Invalid image filename.")

    extension = filename.rsplit(".", 1)[1].lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError("Unsupported image format.")

    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    unique_filename = f"{uuid.uuid4().hex}.{extension}"

    file.save(os.path.join(UPLOAD_FOLDER, unique_filename))

    return unique_filename


def setup_database():
    db = get_db()
    with open(os.path.join(BASE_DIR, "schema.sql"), "r", encoding="utf-8") as file:
        db.executescript(file.read())
    if db.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
        with open(os.path.join(BASE_DIR, "seed.sql"), "r", encoding="utf-8") as file:
            db.executescript(file.read())
    # Older databases have no `code` column yet: add it, give every product a unique 5-digit code
    columns = [row["name"] for row in db.execute("PRAGMA table_info(products)")]
    if "code" not in columns:
        db.execute("ALTER TABLE products ADD COLUMN code INTEGER")
    used = [row["code"] for row in db.execute("SELECT code FROM products WHERE code IS NOT NULL")]
    generator = ProductCodeGenerator(used)
    for row in db.execute("SELECT id FROM products WHERE code IS NULL").fetchall():
        db.execute("UPDATE products SET code = ? WHERE id = ?", (generator.next_code(), row["id"]))
    db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_products_code ON products(code)")
    if db.execute("SELECT COUNT(*) FROM admins").fetchone()[0] == 0:
        db.execute(
            "INSERT INTO admins (username, password_hash) VALUES (?, ?)",
            ("admin", generate_password_hash(os.environ.get("ADMIN_PASSWORD", "admin123"))),
        )
    db.commit()
    db.close()
    for message in ProductChecker().find_duplicates(all_menu_items()):
        print("WARNING duplicate product:", message)


def row_to_item(row):
    return make_item(row["category"], row["name"], row["price"], row["description"], row["code"])


def all_menu_items(exclude_id=None):
    db = get_db()
    rows = db.execute("SELECT * FROM products ORDER BY id").fetchall()
    db.close()
    return [row_to_item(r) for r in rows if r["id"] != exclude_id]


def get_products(category=None, include_unavailable=False):
    db = get_db()

    extra = "" if include_unavailable else " AND availability = 1"

    category_order = """
        ORDER BY
            CASE LOWER(category)
                WHEN 'coffee' THEN 1
                WHEN 'bakery' THEN 2
                WHEN 'breakfast' THEN 3
                ELSE 4
            END,
            name COLLATE NOCASE
    """

    if category and category != "all":
        products = db.execute(
            f"SELECT * FROM products WHERE category = ?{extra} {category_order}",
            (category,)
        ).fetchall()
    else:
        products = db.execute(
            f"SELECT * FROM products WHERE 1=1{extra} {category_order}"
        ).fetchall()

    db.close()
    return products



def get_product(product_id, include_unavailable=False):
    db = get_db()
    extra = "" if include_unavailable else " AND availability = 1"
    product = db.execute(f"SELECT * FROM products WHERE id = ?{extra}", (product_id,)).fetchone()
    db.close()
    return product


def cart_items():
    cart = session.get("cart", {})
    items = []
    total = 0
    for product_id, quantity in cart.items():
        product = get_product(product_id)
        if product:
            line_total = product["price"] * quantity
            items.append({"product": product, "quantity": quantity, "line_total": line_total})
            total += line_total
    return items, total


def find_order(order_number):
    db = get_db()
    order = db.execute("SELECT * FROM orders WHERE order_number = ?", (order_number,)).fetchone()
    items = []
    if order:
        items = db.execute("SELECT * FROM order_items WHERE order_id = ?", (order["id"],)).fetchall()
    db.close()
    return order, items


def admin_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "admin_id" not in session:
            return redirect(url_for("admin_login"))
        return view(*args, **kwargs)
    return wrapped_view


@app.context_processor
def add_common_values():
    cart = session.get("cart", {})
    return {
        "cart_count": sum(cart.values()),
        "admin_logged_in": "admin_id" in session,
        "year": datetime.now().year,
    }


def storefront():
    category = request.args.get("category", "all")
    return render_template(
        "index.html",
        products=get_products(category),
        categories=CATEGORIES,
        selected=category,
        hero_image=HERO_IMAGE,
    )


@app.route("/")
def home():
    return storefront()


@app.route("/menu")
def menu():
    return storefront()


@app.route("/product/<int:product_id>")
def product(product_id):
    item = get_product(product_id)
    if not item:
        abort(404)
    prep = make_item(item["category"], item["name"], item["price"]).prep_label()
    return render_template("product.html", product=item, prep=prep)


@app.post("/cart/add/<int:product_id>")
def add_to_cart(product_id):
    item = get_product(product_id)
    if not item:
        abort(404)
    cart = session.get("cart", {})
    key = str(product_id)
    cart[key] = cart.get(key, 0) + max(1, int(request.form.get("quantity", 1)))
    session["cart"] = cart
    if request.headers.get("X-Requested-With") == "fetch":
        return jsonify(count=sum(cart.values()), name=item["name"])
    return redirect((request.referrer or url_for("menu")).split("#")[0] + "#menu")


@app.route("/cart")
def cart():
    items, total = cart_items()
    return render_template("cart.html", items=items, total=total)


@app.post("/cart/update")
def update_cart():
    cart = session.get("cart", {})
    for product_id in list(cart):
        try:
            quantity = int(request.form.get(f"quantity_{product_id}", cart[product_id]))
        except ValueError:
            quantity = cart[product_id]            # ignore text that is not a number
        if quantity <= 0:
            cart.pop(product_id)
        else:
            cart[product_id] = min(quantity, 99)
    session["cart"] = cart
    if request.headers.get("X-Requested-With") == "fetch":     # auto-update from the cart page
        items, total = cart_items()
        return jsonify(count=sum(cart.values()), total=total,
                       lines={str(i["product"]["id"]): {"quantity": i["quantity"], "line_total": i["line_total"]} for i in items})
    return redirect(url_for("cart"))


@app.route("/cart/remove/<int:product_id>", methods=["GET", "POST"])
def remove_from_cart(product_id):
    cart = session.get("cart", {})
    cart.pop(str(product_id), None)
    session["cart"] = cart
    return redirect(url_for("cart"))


def save_paid_order(pending, items, total, payment, reference):
    """Build an Order and save it after the payment is approved. Returns the order number."""
    customer = Customer(pending["customer_name"], pending["contact_number"], pending["order_type"],
                        pending["table_number"], pending["notes"])
    lines = [OrderLine(i["product"]["id"], i["product"]["name"], i["product"]["price"], i["quantity"]) for i in items]
    order = Order(customer, lines, payment, reference)
    db = get_db()
    cursor = db.execute(
        """INSERT INTO orders (order_number, transaction_reference, customer_name, contact_number, order_type, table_number, notes, subtotal, total, payment_method, payment_status, order_status, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Paid', 'Pending', ?)""",
        (order.order_number, order.reference, customer.name, customer.contact_number, customer.order_type,
         customer.table_number, customer.notes, order.total, order.total, order.payment_label, order.created_at),
    )
    for line in order.lines:
        db.execute(
            """INSERT INTO order_items (order_id, product_id, product_name, quantity, price, subtotal)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (cursor.lastrowid, line.product_id, line.name, line.quantity, line.price, line.subtotal),
        )
    db.commit()
    db.close()
    return order.order_number


@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    items, total = cart_items()
    if not items:
        return redirect(url_for("cart"))
    if request.method == "POST":
        customer_name = request.form.get("customer_name", "").strip()
        contact_number = request.form.get("contact_number", "").strip()
        order_type = request.form.get("order_type", "Takeout")
        table_number = request.form.get("table_number", "").strip()
        notes = request.form.get("notes", "").strip()
        method = request.form.get("payment_method", "gcash")
        if not customer_name or not contact_number:
            return render_template("checkout.html", items=items, total=total, form=request.form, error="Please enter your name and contact number.")
        if order_type == "Dine-in" and not table_number:
            return render_template("checkout.html", items=items, total=total, form=request.form, error="Please enter your table number for dine-in.")
        details = {"customer_name": customer_name, "contact_number": contact_number, "order_type": order_type,
                   "table_number": table_number, "notes": notes}
        if method == "card":
            payment = CardPayment(request.form.get("card_number"), request.form.get("card_expiry"),
                                  request.form.get("card_cvc"), request.form.get("card_name"))
            problem = payment.check()
            if not problem:
                try:
                    reference = payment.pay(total)
                except PaymentDeclined as declined:
                    problem = str(declined)
            if problem:
                return render_template("checkout.html", items=items, total=total, form=request.form, error=problem)
            order_number = save_paid_order(details, items, total, payment, reference)
            session["cart"] = {}
            session.pop("pending_gcash", None)
            return redirect(url_for("receipt", order_number=order_number))
        payment = GCashPayment(request.form.get("gcash_number", ""))
        problem = payment.check()
        if problem:
            return render_template("checkout.html", items=items, total=total, form=request.form, error=problem)
        session["pending_gcash"] = {**details, "gcash_number": payment.number}
        return redirect(url_for("gcash_pay"))
    error = "GCash payment was cancelled. You can try again." if request.args.get("cancelled") else None
    return render_template("checkout.html", items=items, total=total, form=session.get("pending_gcash", {}), error=error)


@app.route("/gcash/pay", methods=["GET", "POST"])
def gcash_pay():
    pending = session.get("pending_gcash")
    items, total = cart_items()
    if not pending or not items:
        return redirect(url_for("checkout"))
    payment = GCashPayment(pending["gcash_number"])
    error = None
    if request.method == "POST":
        if request.form.get("action") == "cancel":
            return redirect(url_for("checkout", cancelled=1))
        try:
            reference = payment.pay(total)
        except PaymentDeclined as problem:
            error = str(problem)
        else:
            order_number = save_paid_order(pending, items, total, payment, reference)
            session["cart"] = {}
            session.pop("pending_gcash", None)
            return redirect(url_for("receipt", order_number=order_number))
    return render_template("gcash_pay.html", items=items, total=total, masked=payment.masked, error=error)


@app.route("/receipt/<order_number>")
def receipt(order_number):
    order, items = find_order(order_number)
    if not order:
        abort(404)
    return render_template("receipt.html", order=order, items=items)


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        db = get_db()
        admin = db.execute("SELECT * FROM admins WHERE username = ?", (username,)).fetchone()
        db.close()
        if admin and check_password_hash(admin["password_hash"], password):
            session["admin_id"] = admin["id"]
            session["admin_username"] = admin["username"]
            return redirect(url_for("admin_dashboard"))
        return render_template("admin_login.html", error="Incorrect username or password.")
    return render_template("admin_login.html", error=None)


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_id", None)
    session.pop("admin_username", None)
    return redirect(url_for("home"))


@app.route("/admin")
@admin_required
def admin_dashboard():
    db = get_db()
    stats = {
        "orders": db.execute("SELECT COUNT(*) FROM orders").fetchone()[0],
        "products": db.execute("SELECT COUNT(*) FROM products").fetchone()[0],
        "pending": db.execute("SELECT COUNT(*) FROM orders WHERE order_status = 'Pending'").fetchone()[0],
        "completed": db.execute("SELECT COUNT(*) FROM orders WHERE order_status = 'Completed'").fetchone()[0],
        "sales": db.execute("SELECT COALESCE(SUM(total), 0) FROM orders WHERE order_status != 'Cancelled'").fetchone()[0],
    }
    products = db.execute("SELECT * FROM products ORDER BY id").fetchall()
    orders = db.execute("SELECT * FROM orders ORDER BY id DESC").fetchall()
    db.close()
    duplicates = ProductChecker().find_duplicates([row_to_item(p) for p in products])
    return render_template(
        "admin_dashboard.html", stats=stats, products=products, orders=orders, duplicates=duplicates)



def read_product_form():
    """Build a MenuItem from the admin form (this also checks the price). Returns (item, error)."""
    f = request.form
    try:
        item = make_item(f["category"].strip(), f["name"], float(f["price"]), f["description"])
    except ValueError as problem:
        return None, "Price must be a positive number." if "could not convert" in str(problem) else str(problem)
    return item, None


@app.post("/admin/products/add")
@admin_required
def admin_add_product():
    # 1. Check name, description and price first, so a rejected product never saves an image
    item, error = read_product_form()
    errors = [error] if error else ProductChecker().validate(item, all_menu_items())
    if errors:
        for message in errors:
            flash(message, "error")
        return redirect(url_for("admin_dashboard"))

    try:
        image_filename = save_product_image(request.files.get("image"))

        if not image_filename:
            return "Please select a product image.", 400

        db = get_db()
        used = [row["code"] for row in db.execute("SELECT code FROM products WHERE code IS NOT NULL")]
        code = ProductCodeGenerator(used).next_code()      # unique 5-digit code

        db.execute(
            """INSERT INTO products
            (name, description, price, image, category, availability, code)
            VALUES (?, ?, ?, ?, ?, 1, ?)""",
            (
                item.name.strip(),
                item.description.strip(),
                item.get_price(),
                image_filename,
                request.form["category"].strip(),
                code
            )
        )

        db.commit()
        db.close()

    except ValueError as error:
        return str(error), 400

    flash(f"Added {item.name.strip()} with code {code}.", "ok")
    return redirect(url_for("admin_dashboard"))


@app.post("/admin/products/<int:product_id>/edit")
@admin_required
def admin_edit_product(product_id):
    db = get_db()

    product = db.execute(
        "SELECT * FROM products WHERE id = ?",
        (product_id,)
    ).fetchone()

    if not product:
        db.close()
        abort(404)

    # Check name, description and price against all OTHER products before saving anything
    item, error = read_product_form()
    errors = [error] if error else ProductChecker().validate(item, all_menu_items(exclude_id=product_id))
    if errors:
        db.close()
        for message in errors:
            flash(message, "error")
        return redirect(url_for("admin_dashboard"))

    try:
        uploaded_file = request.files.get("image")

        new_image = save_product_image(uploaded_file)

        image_filename = new_image or product["image"]

        db.execute(
            """UPDATE products
            SET name = ?, description = ?, price = ?,
                image = ?, category = ?, availability = ?
            WHERE id = ?""",
            (
                item.name.strip(),
                item.description.strip(),
                item.get_price(),
                image_filename,
                request.form["category"].strip(),
                int(request.form.get("availability", 0)),
                product_id
            )
        )

        db.commit()

    except ValueError as error:
        db.close()
        return str(error), 400

    db.close()

    flash("Product saved.", "ok")
    return redirect(url_for("admin_dashboard"))


@app.post("/admin/products/<int:product_id>/delete")
@admin_required
def admin_delete_product(product_id):
    db = get_db()
    db.execute("DELETE FROM products WHERE id = ?", (product_id,))
    db.commit()
    db.close()
    return redirect(url_for("admin_dashboard"))


@app.post("/admin/orders/<int:order_id>/status")
@admin_required
def admin_update_order(order_id):
    db = get_db()
    db.execute("UPDATE orders SET order_status = ?, payment_status = ? WHERE id = ?", (request.form["order_status"], request.form["payment_status"], order_id))
    db.commit()
    db.close()
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/orders/<order_number>/receipt")
@admin_required
def cafe_receipt(order_number):
    order, items = find_order(order_number)
    if not order:
        abort(404)
    return render_template("cafe_receipt.html", order=order, items=items)


setup_database()  

if __name__ == "__main__":
    app.run(debug=True, port=5000)
