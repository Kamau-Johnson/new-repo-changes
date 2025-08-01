# THIS IS THE FINAL, COMPLETE db_setup.py
# IT CREATES ALL TABLES AND INSERTS THE NECESSARY SAMPLE DATA.

import mysql.connector
from mysql.connector import Error

DB_CONFIG = { "host": "localhost", "port": 3307, "user": "root", "password": "" }
DB_NAME = "edugradedb"

def run_query(cursor, query, message):
    try:
        for _ in cursor.execute(query, multi=True): pass
        print(f"-> SUCCESS: {message}")
    except Error as e:
        print(f"-> FAILED: {message} | Error: {e}")

def setup_database():
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        cursor = connection.cursor()
        
        print(f"Creating database '{DB_NAME}' if it does not exist...")
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        cursor.execute(f"USE {DB_NAME}")
        print("-> Success: Database is ready.\n")

        tables = {
            'teachers': """
                CREATE TABLE IF NOT EXISTS teachers (
                    teachID INT PRIMARY KEY AUTO_INCREMENT, teachname VARCHAR(255) NOT NULL,
                    email VARCHAR(100) NOT NULL UNIQUE, phonenumber VARCHAR(20),
                    gender VARCHAR(50) NOT NULL, class TEXT NOT NULL
                ) ENGINE=InnoDB; """,
            'students': """
                CREATE TABLE IF NOT EXISTS students (
                    studID INT PRIMARY KEY AUTO_INCREMENT, admno VARCHAR(50) NOT NULL UNIQUE,
                    studname VARCHAR(255) NOT NULL, gender VARCHAR(50) NOT NULL,
                    dob DATE NOT NULL, class VARCHAR(100) NOT NULL,
                    teachID INT, FOREIGN KEY (teachID) REFERENCES teachers(teachID) ON DELETE SET NULL
                ) ENGINE=InnoDB; """,
            'classes': """
                 CREATE TABLE IF NOT EXISTS classes (
                    classID INT PRIMARY KEY AUTO_INCREMENT,
                    classname VARCHAR(100) NOT NULL
                ) ENGINE=InnoDB; """,
            'login': """
                CREATE TABLE IF NOT EXISTS login (
                    loginID INT PRIMARY KEY AUTO_INCREMENT, username VARCHAR(50) NOT NULL UNIQUE,
                    password VARCHAR(255) NOT NULL, teachID INT,
                    FOREIGN KEY (teachID) REFERENCES teachers(teachID) ON DELETE CASCADE
                ) ENGINE=InnoDB; """,
             'marks': """
                CREATE TABLE IF NOT EXISTS marks (
                    markID INT PRIMARY KEY AUTO_INCREMENT,
                    studID INT NOT NULL, ovrscore INT, meanscore INT, remark TEXT,
                    term VARCHAR(20) NOT NULL, year YEAR NOT NULL,
                    marks_details JSON, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY (studID) REFERENCES students(studID) ON DELETE CASCADE,
                    UNIQUE KEY student_term_year_unique (studID, term, year)
                ) ENGINE=InnoDB; """
        }
        
        for name, query in tables.items():
            run_query(cursor, query, f"Creating table '{name}'")
        
        print("\n--- POPULATING DATABASE WITH SAMPLE DATA ---")
        
        class_inserts = """
            INSERT IGNORE INTO classes (classID, classname) VALUES
            (1, 'grade 1A'), (2, 'grade 1B'), (3, 'grade 2A'), (4, 'grade 2B'),
            (5, 'grade 3A'), (6, 'grade 3B'), (7, 'grade 4A'), (8, 'grade 4B'),
            (9, 'grade 5A'), (10, 'grade 5B');
        """
        run_query(cursor, class_inserts, "Inserting sample classes for dropdown")
        
        connection.commit()
        cursor.close()
        connection.close()
        print("\n✅ Database setup and population completed successfully!")
        
    except Error as e:
        print(f"❌ DATABASE ERROR: {e}")

if __name__ == "__main__":
    setup_database()