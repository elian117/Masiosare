from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .manager import DatabaseManager


def setup_demo_database(db_manager: 'DatabaseManager'):
    """
    Create demo database with sample e-commerce data
    
    Args:
        db_manager: DatabaseManager instance
    """
    db_manager.connect()
    cursor = db_manager.connection.cursor()
    
    print("Creating demo database tables...")
    
    # Create tables
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            category_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            product_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            category_id INTEGER,
            price REAL,
            stock_quantity INTEGER,
            FOREIGN KEY (category_id) REFERENCES categories(category_id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            customer_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT,
            city TEXT,
            country TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            order_id INTEGER PRIMARY KEY,
            customer_id INTEGER,
            order_date TEXT,
            total_amount REAL,
            status TEXT,
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS order_items (
            order_item_id INTEGER PRIMARY KEY,
            order_id INTEGER,
            product_id INTEGER,
            quantity INTEGER,
            unit_price REAL,
            FOREIGN KEY (order_id) REFERENCES orders(order_id),
            FOREIGN KEY (product_id) REFERENCES products(product_id)
        )
    """)
    
    print("Inserting sample data...")
    
    # Insert categories
    categories = [
        (1, 'Electronics', 'Electronic devices and accessories'),
        (2, 'Books', 'Physical and digital books'),
        (3, 'Clothing', 'Apparel and accessories'),
        (4, 'Home & Garden', 'Home improvement and garden supplies'),
        (5, 'Sports', 'Sports equipment and accessories')
    ]
    cursor.executemany("INSERT OR IGNORE INTO categories VALUES (?, ?, ?)", categories)
    
    # Insert products
    products = [
        (1, 'Laptop Pro 15', 1, 1299.99, 15),
        (2, 'Smartphone X', 1, 899.99, 25),
        (3, 'Wireless Headphones', 1, 149.99, 50),
        (4, 'USB-C Hub', 1, 49.99, 100),
        (5, 'Python Programming Guide', 2, 49.99, 75),
        (6, 'Data Science Handbook', 2, 59.99, 60),
        (7, 'Machine Learning Basics', 2, 45.99, 80),
        (8, 'T-Shirt Classic', 3, 19.99, 200),
        (9, 'Jeans Denim', 3, 79.99, 150),
        (10, 'Winter Jacket', 3, 129.99, 75),
        (11, 'Garden Tools Set', 4, 89.99, 30),
        (12, 'LED Light Bulbs (4-pack)', 4, 24.99, 120),
        (13, 'Running Shoes', 5, 109.99, 60),
        (14, 'Yoga Mat', 5, 29.99, 90)
    ]
    cursor.executemany("INSERT OR IGNORE INTO products VALUES (?, ?, ?, ?, ?)", products)
    
    # Insert customers
    customers = [
        (1, 'John Doe', 'john.doe@example.com', 'New York', 'USA'),
        (2, 'Jane Smith', 'jane.smith@example.com', 'Los Angeles', 'USA'),
        (3, 'Bob Johnson', 'bob.j@example.com', 'Chicago', 'USA'),
        (4, 'Alice Williams', 'alice.w@example.com', 'Houston', 'USA'),
        (5, 'Charlie Brown', 'charlie.b@example.com', 'Phoenix', 'USA')
    ]
    cursor.executemany("INSERT OR IGNORE INTO customers VALUES (?, ?, ?, ?, ?)", customers)
    
    # Insert orders
    orders = [
        (1, 1, '2024-01-15', 1449.98, 'Completed'),
        (2, 2, '2024-01-16', 229.98, 'Completed'),
        (3, 1, '2024-01-17', 899.99, 'Shipped'),
        (4, 3, '2024-01-18', 109.98, 'Completed'),
        (5, 2, '2024-01-20', 1379.98, 'Processing'),
        (6, 4, '2024-01-22', 159.98, 'Completed'),
        (7, 5, '2024-01-23', 89.99, 'Shipped'),
        (8, 1, '2024-01-25', 49.99, 'Completed')
    ]
    cursor.executemany("INSERT OR IGNORE INTO orders VALUES (?, ?, ?, ?, ?)", orders)
    
    # Insert order items
    order_items = [
        (1, 1, 1, 1, 1299.99),
        (2, 1, 3, 1, 149.99),
        (3, 2, 8, 3, 19.99),
        (4, 2, 14, 5, 29.99),
        (5, 3, 2, 1, 899.99),
        (6, 4, 5, 1, 49.99),
        (7, 4, 6, 1, 59.99),
        (8, 5, 1, 1, 1299.99),
        (9, 5, 4, 1, 49.99),
        (10, 5, 7, 1, 29.99),
        (11, 6, 13, 1, 109.99),
        (12, 6, 14, 1, 49.99),
        (13, 7, 11, 1, 89.99),
        (14, 8, 4, 1, 49.99)
    ]
    cursor.executemany("INSERT OR IGNORE INTO order_items VALUES (?, ?, ?, ?, ?)", order_items)
    
    db_manager.connection.commit()
    cursor.close()
    
    print("✓ Demo database created successfully")
    print("  - 5 categories")
    print("  - 14 products")
    print("  - 5 customers")
    print("  - 8 orders with items\n")
