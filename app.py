from flask import Flask, jsonify, request, render_template, g
import sqlite3, os

app = Flask(__name__)
DB_PATH = os.path.join(os.path.dirname(__file__), 'inventory.db')

#DATABASE

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    db = g.pop('db', None)
    if db:
        db.close()

def init_db():
    """Create tables and seed data if DB doesn't exist yet."""
    if os.path.exists(DB_PATH):
        return
    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript("""
        CREATE TABLE Suppliers (
            SupplierID   INTEGER PRIMARY KEY AUTOINCREMENT,
            SupplierName TEXT    NOT NULL,
            Contact      TEXT,
            Address      TEXT
        );

        CREATE TABLE Products (
            ProductID   INTEGER PRIMARY KEY AUTOINCREMENT,
            SupplierID  INTEGER,
            ProductName TEXT    NOT NULL,
            Price       REAL    DEFAULT 0,
            StockQty    INTEGER DEFAULT 0,
            FOREIGN KEY (SupplierID) REFERENCES Suppliers(SupplierID)
        );

        CREATE TABLE Purchases (
            PurchaseID   INTEGER PRIMARY KEY AUTOINCREMENT,
            ProductID    INTEGER,
            Quantity     INTEGER,
            PurchaseDate TEXT DEFAULT (date('now')),
            FOREIGN KEY (ProductID) REFERENCES Products(ProductID)
        );

        CREATE TABLE Sales (
            SaleID    INTEGER PRIMARY KEY AUTOINCREMENT,
            ProductID INTEGER,
            Quantity  INTEGER,
            SaleDate  TEXT DEFAULT (date('now')),
            FOREIGN KEY (ProductID) REFERENCES Products(ProductID)
        );

        INSERT INTO Suppliers (SupplierName, Contact, Address) VALUES
          ('TechSupplies Co.',  '0300-1234567', 'Lahore, Punjab'),
          ('GlobalGoods Ltd.',  '0311-9876543', 'Karachi, Sindh'),
          ('FastTrack Traders', '0321-5556677', 'Islamabad'),
          ('PrimeParts Inc.',   '0333-1122334', 'Faisalabad, Punjab'),
          ('ZenithZone',        '0345-9988776', 'Multan, Punjab');

        INSERT INTO Products (SupplierID, ProductName, Price, StockQty) VALUES
          (1, 'USB Hub 4-Port',    450.00,  120),
          (1, 'Wireless Keyboard', 1200.00,  85),
          (2, 'HDMI Cable 2m',     350.00,  200),
          (3, 'Office Chair',      8500.00,  30),
          (4, 'Laptop Stand',      1800.00,  60),
          (5, 'Monitor 24-inch',  32000.00,  15);

        INSERT INTO Purchases (ProductID, Quantity, PurchaseDate) VALUES
          (1, 50, '2024-11-01'),
          (2, 30, '2024-11-05'),
          (3, 80, '2024-11-10'),
          (4, 10, '2024-11-15'),
          (5, 25, '2024-11-20'),
          (6,  5, '2024-11-25');

        INSERT INTO Sales (ProductID, Quantity, SaleDate) VALUES
          (1, 20, '2024-12-01'),
          (2, 10, '2024-12-03'),
          (3, 35, '2024-12-07'),
          (4,  3, '2024-12-10'),
          (5, 15, '2024-12-15'),
          (6,  2, '2024-12-20');
    """)
    con.commit()
    con.close()

def rows_to_list(rows):
    return [dict(r) for r in rows]

#FRONTEND

@app.route('/')
def index():
    return render_template('index.html')

#DASHBOARD

@app.route('/api/dashboard')
def dashboard():
    db = get_db()
    stats = {
        'products':  db.execute('SELECT COUNT(*) FROM Products').fetchone()[0],
        'suppliers': db.execute('SELECT COUNT(*) FROM Suppliers').fetchone()[0],
        'purchases': db.execute('SELECT COUNT(*) FROM Purchases').fetchone()[0],
        'sales':     db.execute('SELECT COUNT(*) FROM Sales').fetchone()[0],
    }
    low_stock = rows_to_list(db.execute(
        'SELECT ProductName, StockQty FROM Products WHERE StockQty < 20 ORDER BY StockQty ASC'
    ).fetchall())
    recent_sales = rows_to_list(db.execute("""
        SELECT p.ProductName, s.Quantity, s.SaleDate
        FROM Sales s JOIN Products p ON s.ProductID=p.ProductID
        ORDER BY s.SaleDate DESC LIMIT 6
    """).fetchall())
    chart = rows_to_list(db.execute("""
        SELECT p.ProductName, SUM(s.Quantity) AS TotalSold
        FROM Sales s JOIN Products p ON s.ProductID=p.ProductID
        GROUP BY p.ProductName ORDER BY TotalSold DESC
    """).fetchall())
    return jsonify(stats=stats, low_stock=low_stock, recent_sales=recent_sales, chart=chart)

#PRODUCTS 

@app.route('/api/products')
def get_products():
    search = request.args.get('search', '')
    like   = f'%{search}%'
    rows = rows_to_list(get_db().execute("""
        SELECT p.ProductID, p.ProductName, s.SupplierName, p.SupplierID, p.Price, p.StockQty
        FROM Products p LEFT JOIN Suppliers s ON p.SupplierID=s.SupplierID
        WHERE p.ProductName LIKE ? OR s.SupplierName LIKE ?
        ORDER BY p.ProductName
    """, (like, like)).fetchall())
    return jsonify(rows)

@app.route('/api/products', methods=['POST'])
def add_product():
    d  = request.json
    db = get_db()
    db.execute(
        'INSERT INTO Products (SupplierID, ProductName, Price, StockQty) VALUES (?,?,?,?)',
        (d['supplier_id'], d['name'], d['price'], d['stock'])
    )
    db.commit()
    return jsonify(ok=True, message='Product added successfully ✓')

@app.route('/api/products/<int:pid>', methods=['PUT'])
def update_product(pid):
    d  = request.json
    db = get_db()
    db.execute(
        'UPDATE Products SET ProductName=?, SupplierID=?, Price=?, StockQty=? WHERE ProductID=?',
        (d['name'], d['supplier_id'], d['price'], d['stock'], pid)
    )
    db.commit()
    return jsonify(ok=True, message='Product updated successfully ✓')

@app.route('/api/products/<int:pid>', methods=['DELETE'])
def delete_product(pid):
    db = get_db()
    db.execute('DELETE FROM Sales    WHERE ProductID=?', (pid,))
    db.execute('DELETE FROM Purchases WHERE ProductID=?', (pid,))
    db.execute('DELETE FROM Products  WHERE ProductID=?', (pid,))
    db.commit()
    return jsonify(ok=True, message='Product deleted')

#SUPPLIERS

@app.route('/api/suppliers')
def get_suppliers():
    search = request.args.get('search', '')
    like   = f'%{search}%'
    rows = rows_to_list(get_db().execute("""
        SELECT s.SupplierID, s.SupplierName, s.Contact, s.Address,
               COUNT(p.ProductID) AS ProductCount
        FROM Suppliers s LEFT JOIN Products p ON p.SupplierID=s.SupplierID
        WHERE s.SupplierName LIKE ?
        GROUP BY s.SupplierID ORDER BY s.SupplierName
    """, (like,)).fetchall())
    return jsonify(rows)

@app.route('/api/suppliers', methods=['POST'])
def add_supplier():
    d  = request.json
    db = get_db()
    db.execute(
        'INSERT INTO Suppliers (SupplierName, Contact, Address) VALUES (?,?,?)',
        (d['name'], d.get('contact',''), d.get('address',''))
    )
    db.commit()
    return jsonify(ok=True, message='Supplier added ✓')

@app.route('/api/suppliers/<int:sid>', methods=['PUT'])
def update_supplier(sid):
    d  = request.json
    db = get_db()
    db.execute(
        'UPDATE Suppliers SET SupplierName=?, Contact=?, Address=? WHERE SupplierID=?',
        (d['name'], d.get('contact',''), d.get('address',''), sid)
    )
    db.commit()
    return jsonify(ok=True, message='Supplier updated ✓')

@app.route('/api/suppliers/<int:sid>', methods=['DELETE'])
def delete_supplier(sid):
    db = get_db()
    count = db.execute('SELECT COUNT(*) FROM Products WHERE SupplierID=?', (sid,)).fetchone()[0]
    if count > 0:
        return jsonify(ok=False, message='Cannot delete: supplier has products linked'), 400
    db.execute('DELETE FROM Suppliers WHERE SupplierID=?', (sid,))
    db.commit()
    return jsonify(ok=True, message='Supplier deleted')

#  PURCHASES 

@app.route('/api/purchases')
def get_purchases():
    rows = rows_to_list(get_db().execute("""
        SELECT pu.PurchaseID, p.ProductName, s.SupplierName, pu.Quantity, pu.PurchaseDate
        FROM Purchases pu
        JOIN Products p  ON pu.ProductID=p.ProductID
        LEFT JOIN Suppliers s ON p.SupplierID=s.SupplierID
        ORDER BY pu.PurchaseDate DESC
    """).fetchall())
    return jsonify(rows)

@app.route('/api/purchases', methods=['POST'])
def add_purchase():
    d  = request.json
    db = get_db()
    db.execute(
        'INSERT INTO Purchases (ProductID, Quantity, PurchaseDate) VALUES (?,?,?)',
        (d['product_id'], d['quantity'], d['date'])
    )
    db.execute(
        'UPDATE Products SET StockQty=StockQty+? WHERE ProductID=?',
        (d['quantity'], d['product_id'])
    )
    db.commit()
    return jsonify(ok=True, message=f"Purchase recorded — Stock updated +{d['quantity']} ✓")

@app.route('/api/purchases/<int:pid>', methods=['DELETE'])
def delete_purchase(pid):
    db = get_db()
    db.execute('DELETE FROM Purchases WHERE PurchaseID=?', (pid,))
    db.commit()
    return jsonify(ok=True, message='Purchase deleted')

#SALES

@app.route('/api/sales')
def get_sales():
    rows = rows_to_list(get_db().execute("""
        SELECT s.SaleID, p.ProductName, p.Price, s.Quantity, s.SaleDate, s.ProductID
        FROM Sales s JOIN Products p ON s.ProductID=p.ProductID
        ORDER BY s.SaleDate DESC
    """).fetchall())
    return jsonify(rows)

@app.route('/api/sales', methods=['POST'])
def add_sale():
    d   = request.json
    db  = get_db()
    row = db.execute('SELECT StockQty FROM Products WHERE ProductID=?', (d['product_id'],)).fetchone()
    if not row:
        return jsonify(ok=False, message='Product not found'), 404
    if d['quantity'] > row['StockQty']:
        return jsonify(ok=False, message=f"Insufficient stock! Available: {row['StockQty']}"), 400
    db.execute(
        'INSERT INTO Sales (ProductID, Quantity, SaleDate) VALUES (?,?,?)',
        (d['product_id'], d['quantity'], d['date'])
    )
    db.execute(
        'UPDATE Products SET StockQty=StockQty-? WHERE ProductID=?',
        (d['quantity'], d['product_id'])
    )
    db.commit()
    return jsonify(ok=True, message=f"Sale recorded — Stock reduced by {d['quantity']} ✓")

@app.route('/api/sales/<int:sid>', methods=['DELETE'])
def delete_sale(sid):
    db = get_db()
    db.execute('DELETE FROM Sales WHERE SaleID=?', (sid,))
    db.commit()
    return jsonify(ok=True, message='Sale deleted')

#REPORTS

@app.route('/api/reports')
def get_reports():
    db = get_db()
    sales_summary = rows_to_list(db.execute("""
        SELECT p.ProductName, SUM(s.Quantity) AS TotalSold, COUNT(s.SaleID) AS NumSales
        FROM Sales s JOIN Products p ON s.ProductID=p.ProductID
        GROUP BY p.ProductName ORDER BY TotalSold DESC
    """).fetchall())
    purchase_summary = rows_to_list(db.execute("""
        SELECT p.ProductName, SUM(pu.Quantity) AS TotalBought, COUNT(pu.PurchaseID) AS NumPurchases
        FROM Purchases pu JOIN Products p ON pu.ProductID=p.ProductID
        GROUP BY p.ProductName ORDER BY TotalBought DESC
    """).fetchall())
    supplier_summary = rows_to_list(db.execute("""
        SELECT sup.SupplierName, AVG(p.Price) AS AvgPrice,
               MAX(p.Price) AS MaxPrice, MIN(p.Price) AS MinPrice
        FROM Products p JOIN Suppliers sup ON p.SupplierID=sup.SupplierID
        GROUP BY sup.SupplierName
    """).fetchall())
    stock_overview = rows_to_list(db.execute(
        'SELECT ProductName, StockQty, Price FROM Products ORDER BY StockQty ASC'
    ).fetchall())
    return jsonify(
        sales_summary=sales_summary,
        purchase_summary=purchase_summary,
        supplier_summary=supplier_summary,
        stock_overview=stock_overview
    )

#ANALYTICS

@app.route('/api/analytics')
def get_analytics():
    db = get_db()
    stats = {
        'total_products': db.execute('SELECT COUNT(*) FROM Products').fetchone()[0],
        'total_sold':     db.execute('SELECT COALESCE(SUM(Quantity),0) FROM Sales').fetchone()[0],
        'avg_price':      db.execute('SELECT COALESCE(AVG(Price),0) FROM Products').fetchone()[0],
        'max_price':      db.execute('SELECT COALESCE(MAX(Price),0) FROM Products').fetchone()[0],
        'min_price':      db.execute('SELECT COALESCE(MIN(Price),0) FROM Products').fetchone()[0],
    }
    sales_per_product = rows_to_list(db.execute("""
        SELECT p.ProductName, SUM(s.Quantity) AS TotalSold, COUNT(s.SaleID) AS NumSales
        FROM Sales s JOIN Products p ON s.ProductID=p.ProductID
        GROUP BY p.ProductName ORDER BY TotalSold DESC
    """).fetchall())
    purchases_per_supplier = rows_to_list(db.execute("""
        SELECT sup.SupplierName, COUNT(pu.PurchaseID) AS TotalOrders, SUM(pu.Quantity) AS TotalUnits
        FROM Purchases pu
        JOIN Products  p   ON pu.ProductID=p.ProductID
        JOIN Suppliers sup ON p.SupplierID=sup.SupplierID
        GROUP BY sup.SupplierName
        HAVING SUM(pu.Quantity) > 20
        ORDER BY TotalUnits DESC
    """).fetchall())
    left_join = rows_to_list(db.execute("""
        SELECT p.ProductName, p.StockQty, COALESCE(SUM(s.Quantity),0) AS TotalSold
        FROM Products p LEFT JOIN Sales s ON p.ProductID=s.ProductID
        GROUP BY p.ProductName, p.StockQty ORDER BY TotalSold DESC
    """).fetchall())
    three_join = rows_to_list(db.execute("""
        SELECT p.ProductName, sup.SupplierName, s.Quantity, s.SaleDate
        FROM Sales s
        INNER JOIN Products  p   ON s.ProductID=p.ProductID
        INNER JOIN Suppliers sup ON p.SupplierID=sup.SupplierID
        ORDER BY s.SaleDate DESC
    """).fetchall())
    return jsonify(
        stats=stats,
        sales_per_product=sales_per_product,
        purchases_per_supplier=purchases_per_supplier,
        left_join=left_join,
        three_join=three_join
    )

#HELPERS

@app.route('/api/suppliers/list')
def suppliers_list():
    rows = rows_to_list(get_db().execute(
        'SELECT SupplierID as id, SupplierName as name FROM Suppliers ORDER BY SupplierName'
    ).fetchall())
    return jsonify(rows)

@app.route('/api/products/list')
def products_list():
    rows = rows_to_list(get_db().execute(
        'SELECT ProductID as id, ProductName as name FROM Products ORDER BY ProductName'
    ).fetchall())
    return jsonify(rows)

@app.route('/api/products/<int:pid>/stock')
def product_stock(pid):
    row = get_db().execute(
        'SELECT Price, StockQty FROM Products WHERE ProductID=?', (pid,)
    ).fetchone()
    if not row:
        return jsonify(ok=False), 404
    return jsonify(dict(row))

#MAIN

if __name__ == '__main__':
    init_db()
    print("\n✅  IMS is running → http://127.0.0.1:5000\n")
    app.run(debug=True)
