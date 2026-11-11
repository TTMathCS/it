-- The shop: the sample database used in every chapter of the SQL course on it.akadian.ca.
-- It runs unchanged on PostgreSQL and SQLite (tested on PostgreSQL 16.15 and SQLite 3.53).
-- It should also load on MySQL 8 and SQL Server, but that has not been tested.
-- Made-up data. Edge cases are there on purpose: NULL emails and cities, a guest order with no customer,
-- a customer with no orders, a product never sold, a product with no category, tied prices and salaries,
-- an employee with no salary yet, and a duplicated login.

CREATE TABLE customers (
  customer_id INTEGER PRIMARY KEY,
  name        VARCHAR(50) NOT NULL,
  email       VARCHAR(100),
  city        VARCHAR(50),
  country     VARCHAR(50) NOT NULL,
  signup_date DATE NOT NULL
);

CREATE TABLE products (
  product_id INTEGER PRIMARY KEY,
  name       VARCHAR(50) NOT NULL,
  category   VARCHAR(20),
  price      NUMERIC(8,2) NOT NULL
);

CREATE TABLE orders (
  order_id    INTEGER PRIMARY KEY,
  customer_id INTEGER REFERENCES customers (customer_id),
  order_date  DATE NOT NULL,
  status      VARCHAR(10) NOT NULL
);

CREATE TABLE order_items (
  order_id   INTEGER NOT NULL REFERENCES orders (order_id),
  product_id INTEGER NOT NULL REFERENCES products (product_id),
  quantity   INTEGER NOT NULL,
  unit_price NUMERIC(8,2) NOT NULL,
  PRIMARY KEY (order_id, product_id)
);

CREATE TABLE employees (
  employee_id INTEGER PRIMARY KEY,
  name        VARCHAR(50) NOT NULL,
  department  VARCHAR(20) NOT NULL,
  manager_id  INTEGER REFERENCES employees (employee_id),
  salary      INTEGER,
  hire_date   DATE NOT NULL
);

CREATE TABLE logins (
  customer_id INTEGER NOT NULL REFERENCES customers (customer_id),
  login_date  DATE NOT NULL
);

INSERT INTO customers VALUES
  (1,  'Ana Silva',    'ana@example.com',       'Toronto',  'Canada',      '2025-11-03'),
  (2,  'Ben Okafor',   'ben@example.com',       'Lagos',    'Nigeria',     '2025-12-10'),
  (3,  'Chen Wei',     NULL,                    'Shanghai', 'China',       '2026-01-05'),
  (4,  'Dana Kim',     'dana@example.com',      'Seoul',    'South Korea', '2026-01-05'),
  (5,  'Eli Cohen',    'eli@example.com',       NULL,       'Israel',      '2026-01-20'),
  (6,  'Farah Haddad', 'farah@example.com',     'Toronto',  'Canada',      '2026-02-02'),
  (7,  'Gus Novak',    'gus@example.com',       'Prague',   'Czechia',     '2026-02-14'),
  (8,  'Hana Sato',    NULL,                    'Osaka',    'Japan',       '2026-02-28'),
  (9,  'Ivan Petrov',  'ivan@example.com',      'Toronto',  'Canada',      '2026-03-03'),
  (10, 'Ana Silva',    'ana.silva@example.com', 'Lisbon',   'Portugal',    '2026-03-15');

INSERT INTO products VALUES
  (1,  'Desk lamp',     'Home',    24.50),
  (2,  'Notebook',      'Office',   3.25),
  (3,  'Fountain pen',  'Office',  18.00),
  (4,  'Coffee mug',    'Kitchen',  8.75),
  (5,  'Tea kettle',    'Kitchen', 32.00),
  (6,  'Office chair',  'Office', 149.00),
  (7,  'Monitor stand', 'Office',  32.00),
  (8,  'Plant pot',     'Home',    12.25),
  (9,  'Wall clock',    'Home',    24.50),
  (10, 'Gift card',     NULL,      25.00),
  (11, 'Bookend',       'Home',     9.50);

INSERT INTO orders VALUES
  (101, 1,    '2026-01-03', 'shipped'),
  (102, 2,    '2026-01-03', 'shipped'),
  (103, 1,    '2026-01-15', 'shipped'),
  (104, 3,    '2026-01-20', 'cancelled'),
  (105, 4,    '2026-01-28', 'shipped'),
  (106, 2,    '2026-02-02', 'shipped'),
  (107, 5,    '2026-02-02', 'shipped'),
  (108, NULL, '2026-02-10', 'shipped'),
  (109, 6,    '2026-02-14', 'shipped'),
  (110, 1,    '2026-02-20', 'shipped'),
  (111, 7,    '2026-02-21', 'shipped'),
  (112, 4,    '2026-03-01', 'shipped'),
  (113, 2,    '2026-03-05', 'cancelled'),
  (114, 8,    '2026-03-09', 'shipped'),
  (115, 1,    '2026-03-18', 'shipped'),
  (116, 6,    '2026-03-22', 'pending'),
  (117, 10,   '2026-03-25', 'shipped'),
  (118, 3,    '2026-04-01', 'shipped'),
  (119, 5,    '2026-04-02', 'pending'),
  (120, 1,    '2026-04-05', 'shipped');

INSERT INTO order_items VALUES
  (101, 1, 1,  24.50), (101, 2, 3,   3.25),
  (102, 6, 1, 149.00),
  (103, 4, 2,   8.75), (103, 2, 5,   3.25),
  (104, 5, 1,  32.00),
  (105, 3, 1,  18.00), (105, 2, 2,   3.25),
  (106, 7, 1,  32.00), (106, 1, 1,  24.50),
  (107, 8, 3,  12.25),
  (108, 10, 2, 25.00),
  (109, 4, 4,   8.75), (109, 5, 1,  30.00),
  (110, 2, 10,  3.25),
  (111, 9, 1,  24.50), (111, 8, 1,  12.25),
  (112, 6, 1, 149.00), (112, 7, 1,  32.00),
  (113, 3, 2,  18.00),
  (114, 1, 2,  24.50),
  (115, 5, 1,  32.00), (115, 4, 2,   8.75),
  (116, 10, 1, 25.00),
  (117, 3, 1,  18.00), (117, 2, 5,   3.25), (117, 4, 1, 8.75),
  (118, 1, 1,  24.50),
  (119, 8, 2,  12.25),
  (120, 6, 1, 139.00);

INSERT INTO employees VALUES
  (1,  'Maya Rossi',   'Management',  NULL, 180000, '2019-04-01'),
  (2,  'Tom Becker',   'Engineering', 1,    140000, '2020-01-15'),
  (3,  'Priya Nair',   'Engineering', 2,    120000, '2021-03-01'),
  (4,  'Sam Lee',      'Engineering', 2,    120000, '2022-06-15'),
  (5,  'Lucia Gomez',  'Engineering', 2,     95000, '2024-09-01'),
  (6,  'Omar Aziz',    'Sales',       1,    110000, '2020-07-01'),
  (7,  'Nina Berg',    'Sales',       6,     70000, '2023-02-01'),
  (8,  'Raj Patel',    'Sales',       6,     70000, '2023-05-15'),
  (9,  'Zoe Martin',   'Sales',       6,     65000, '2025-01-06'),
  (10, 'Kwame Mensah', 'Support',     1,     75000, '2021-11-01'),
  (11, 'Ella Novak',   'Support',     10,    52000, '2024-02-12'),
  (12, 'Leo Park',     'Support',     10,    NULL,  '2026-01-12');

INSERT INTO logins VALUES
  (1, '2026-03-01'), (1, '2026-03-02'), (1, '2026-03-03'), (1, '2026-03-05'), (1, '2026-03-06'), (1, '2026-03-10'),
  (2, '2026-03-01'), (2, '2026-03-02'), (2, '2026-03-02'), (2, '2026-03-04'),
  (4, '2026-03-03'), (4, '2026-03-04'), (4, '2026-03-05'), (4, '2026-03-06'),
  (6, '2026-03-08');
