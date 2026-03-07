# Table creation
CREATE_USERS_TABLE_PG = """
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    age INTEGER NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
)
"""

CREATE_POSTS_TABLE_PG = """
CREATE TABLE IF NOT EXISTS posts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    title VARCHAR(200) NOT NULL,
    content TEXT DEFAULT '',
    views INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
)
"""

CREATE_TAGS_TABLE_PG = """
CREATE TABLE IF NOT EXISTS tags (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE
)
"""

CREATE_POST_TAGS_TABLE_PG = """
CREATE TABLE IF NOT EXISTS post_tags (
    id SERIAL PRIMARY KEY,
    post_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
)
"""

# SQLite versions
CREATE_USERS_TABLE_SQLITE = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    age INTEGER NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
"""

CREATE_POSTS_TABLE_SQLITE = """
CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    content TEXT DEFAULT '',
    views INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
)
"""

CREATE_TAGS_TABLE_SQLITE = """
CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
)
"""

CREATE_POST_TAGS_TABLE_SQLITE = """
CREATE TABLE IF NOT EXISTS post_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
)
"""

# CRUD queries - PostgreSQL ($1, $2, ...)
INSERT_USER = "INSERT INTO users (name, email, age) VALUES ($1, $2, $3) RETURNING id"
SELECT_USER_BY_ID = "SELECT * FROM users WHERE id = $1"
SELECT_USERS_AGE_GTE = "SELECT * FROM users WHERE age >= $1"
UPDATE_USER_NAME = "UPDATE users SET name = $1 WHERE id = $2"
UPDATE_USERS_BULK = "UPDATE users SET is_active = $1 WHERE age < $2"
DELETE_USER = "DELETE FROM users WHERE id = $1"
FILTER_SIMPLE = "SELECT * FROM users WHERE name = $1"
FILTER_COMPLEX = (
    "SELECT * FROM users WHERE (age >= $1 AND is_active = $2) OR name LIKE $3"
)
ORDER_LIMIT = "SELECT * FROM users ORDER BY created_at DESC LIMIT $1"
JOIN_FILTER = "SELECT p.*, u.* FROM posts p JOIN users u ON p.user_id = u.id WHERE u.age >= $1"

# CRUD queries - SQLite (?, ?, ...)
INSERT_USER_SQLITE = (
    "INSERT INTO users (name, email, age) VALUES (?, ?, ?) RETURNING id"
)
SELECT_USER_BY_ID_SQLITE = "SELECT * FROM users WHERE id = ?"
SELECT_USERS_AGE_GTE_SQLITE = "SELECT * FROM users WHERE age >= ?"
UPDATE_USER_NAME_SQLITE = "UPDATE users SET name = ? WHERE id = ?"
UPDATE_USERS_BULK_SQLITE = "UPDATE users SET is_active = ? WHERE age < ?"
DELETE_USER_SQLITE = "DELETE FROM users WHERE id = ?"
FILTER_SIMPLE_SQLITE = "SELECT * FROM users WHERE name = ?"
FILTER_COMPLEX_SQLITE = (
    "SELECT * FROM users WHERE (age >= ? AND is_active = ?) OR name LIKE ?"
)
ORDER_LIMIT_SQLITE = "SELECT * FROM users ORDER BY created_at DESC LIMIT ?"
JOIN_FILTER_SQLITE = "SELECT p.*, u.* FROM posts p JOIN users u ON p.user_id = u.id WHERE u.age >= ?"

# CRUD queries - MySQL (%s, %s, ...)
INSERT_USER_MYSQL = "INSERT INTO users (name, email, age) VALUES (%s, %s, %s)"
SELECT_USER_BY_ID_MYSQL = "SELECT * FROM users WHERE id = %s"
SELECT_USERS_AGE_GTE_MYSQL = "SELECT * FROM users WHERE age >= %s"
UPDATE_USER_NAME_MYSQL = "UPDATE users SET name = %s WHERE id = %s"
UPDATE_USERS_BULK_MYSQL = "UPDATE users SET is_active = %s WHERE age < %s"
DELETE_USER_MYSQL = "DELETE FROM users WHERE id = %s"
FILTER_SIMPLE_MYSQL = "SELECT * FROM users WHERE name = %s"
FILTER_COMPLEX_MYSQL = (
    "SELECT * FROM users WHERE (age >= %s AND is_active = %s) OR name LIKE %s"
)
ORDER_LIMIT_MYSQL = "SELECT * FROM users ORDER BY created_at DESC LIMIT %s"
JOIN_FILTER_MYSQL = "SELECT p.*, u.* FROM posts p JOIN users u ON p.user_id = u.id WHERE u.age >= %s"

# Common queries (no parameters)
AGGREGATE_COUNT = "SELECT COUNT(*) as count FROM users"
AGGREGATE_MIXED = (
    "SELECT COUNT(*) as count, AVG(age) as avg_age, MAX(age) as max_age FROM users"
)
JOIN_SIMPLE = "SELECT p.*, u.* FROM posts p JOIN users u ON p.user_id = u.id"

# Cleanup
TRUNCATE_USERS = "DELETE FROM users"
TRUNCATE_POSTS = "DELETE FROM posts"
TRUNCATE_TAGS = "DELETE FROM tags"
TRUNCATE_POST_TAGS = "DELETE FROM post_tags"
