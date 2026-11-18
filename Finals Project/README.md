# Crimson Café
### Python / Flask E-Commerce Application

Crimson Café is a café-themed e-commerce web application built using **Python, Flask, SQLite, HTML, CSS, and JavaScript**. It features a modern, minimalist interface inspired by a black and crimson color palette.

The application allows customers to browse café products, add items to their shopping cart, place orders, and complete a simulated checkout process using GCash or credit/debit card payment options. It also includes an administrative section for managing products and customer orders.

---

## Features

### Customer Features
- **Product Catalog** – Browse available café products with images, descriptions, prices, and categories.
- **Category Filtering** – Explore products by category.
- **Shopping Cart** – Add products, update quantities, and manage cart items.
- **Checkout System** – Review orders and calculate the total amount before payment.
- **Payment Simulation** – Choose between GCash and credit/debit card.
- **Order Confirmation** – Receive an order receipt after completing checkout.
- **Responsive Design** – Browse the application on desktop and mobile devices.

### Admin Features
- **Admin Authentication** – Secure login to access the administrative section.
- **Product Management** – Manage café products and their information.
- **Order Management** – View and manage customer orders.

---

## Technologies Used

| Technology | Purpose |
|---|---|
| Python | Main programming language and backend logic |
| Flask | Web application framework |
| SQLite | Database management and data storage |
| SQL | Database structure and initial product records |
| HTML5 | Webpage structure |
| CSS3 | Styling and responsive layouts |
| JavaScript | Client-side interactions, including cart functionality |
| Jinja2 | Dynamic HTML templating |

---

## Getting Started

### Prerequisites
Make sure you have the following installed:
- Python 3.x
- pip (Python package installer)

### Installation

**1. Clone or download the repository.**

**2. Navigate to the project directory.**

```bash
cd "Finals Project"
```

**3. Install the required dependencies.**

```bash
pip install -r requirements.txt
```

**4. Run the Flask application.**

```bash
python app.py
```

**5. Open the application in your browser.**

[http://127.0.0.1:5000](http://127.0.0.1:5000)

---

## Project Structure

```text
Crimson-Cafe/
│
├── app.py                  # Flask application and backend routes
├── models.py               # Object-Oriented Programming classes
├── schema.sql              # Database table definitions
├── seed.sql                # Initial café product data
├── shop.db                 # SQLite database
├── requirements.txt        # Python dependencies
├── Procfile                # Application startup configuration
│
├── templates/
│   ├── base.html            # Shared layout, header, and footer
│   ├── index.html           # Main storefront
│   └── ...                  # Other HTML templates
│
├── static/
│   ├── style.css            # Application styling
│   ├── app.js               # Client-side cart functionality
│   └── img/                 # Product and website images
│
├── check_checkout.py        # Checkout-related checks
└── test_models.py           # OOP model tests
```

---

## Database

Crimson Café uses **SQLite** to store and manage application data.

The database includes the following tables:

| Table | Description |
|---|---|
| `products` | Stores café products, descriptions, prices, and availability. |
| `orders` | Stores customer orders and payment information. |
| `order_items` | Stores individual products associated with each order. |
| `admins` | Stores administrator account information. |

- `schema.sql` defines the database tables.
- `seed.sql` provides the initial café menu data.
- `shop.db` stores the actual database records.

---

## Payment System (Simulation)

The checkout system includes two simulated payment methods:

### GCash
- Customers enter a Philippine mobile number.
- A second confirmation page simulates payment approval through the GCash application.
- Successful payments are recorded as **Paid**.
- A payment reference beginning with `GCASH-` is generated.
- The receipt displays a masked mobile number.

### Credit / Debit Card
- Customers enter their card details.
- Successful payments are processed directly through the application's simulation.
- Only the last four card digits are saved.
- The CVC is never stored.

### Demo Payment Test Values

| Payment Method | Test Value | Expected Result |
|---|---|---|
| GCash | `0900 000 0000` | Declined |
| GCash | Other valid Philippine mobile number | Approved |
| Card | `4242 4242 4242 4242` | Approved |
| Card | `4000 0000 0000 0002` | Declined |

**Important:** This is a payment simulation for demonstration and educational purposes. No actual GCash transactions or card charges are performed. It is not connected to the official GCash or banking payment systems.

---

## Object-Oriented Programming (OOP) Implementation

The application demonstrates the four fundamental principles of Object-Oriented Programming through the classes defined in `models.py`.

### 1. Abstraction
Implemented through the abstract classes:
- `MenuItem`
- `PaymentMethod`

These classes define common structures and required behaviors for their respective subclasses without requiring every implementation detail to be defined in the parent class.

### 2. Inheritance
Implemented through the following class relationships:

- `Drink`, `Pastry`, and `Breakfast` inherit from `MenuItem`.
- `GCashPayment` and `CardPayment` inherit from `PaymentMethod`.

This allows subclasses to reuse common attributes and behaviors from their parent classes.

### 3. Polymorphism
Demonstrated through:
- Different menu item classes implementing their own `prep_minutes` behavior.
- Different payment classes implementing their own `pay()` behavior.

The application can interact with different item and payment types through their shared interfaces.

### 4. Encapsulation
Demonstrated through private attributes:
- Menu item prices.
- GCash mobile numbers.

These attributes are accessed or modified through methods rather than being directly exposed.

---

## Configuration and Deployment Files

| File | Purpose |
|---|---|
| `requirements.txt` | Lists the Python packages required by the application. |
| `Procfile` | Defines the command used by the hosting platform to start the web application. |
| `schema.sql` | Defines the database structure. |
| `seed.sql` | Provides initial database records. |

To change the storefront hero image, update the `HERO_IMAGE` configuration near the top of `app.py`.

---

## Demo Administrator Account

| Field | Credentials |
|---|---|
| Username | `admin` |
| Password | `admin123` |
| Login Page | `/admin/login` |

**Security Note:** The credentials above are intended for local demonstration only. Change the default administrator password and use appropriate security practices before deploying the application publicly.

---

## Project Purpose

Crimson Café was developed as an academic project to demonstrate the practical application of **Object-Oriented Programming using Python** in a small-scale e-commerce system.

By combining Python classes, database management, web development, and simulated payment processing, the project demonstrates how OOP concepts can be applied to build a functional and organized software application.

---

**Developed as an Object-Oriented Programming (OOP) Finals Project.**