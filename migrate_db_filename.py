# migrate_db_filename.py
import sqlite3
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Define database paths (assuming script runs from project root)
SOURCE_DB = "techtree.db"
DEST_DB = "techtree_db.sqlite"

# --- Configuration ---
# Add any tables here that should NOT be cleared in the destination
# before migration (e.g., if they contain essential setup data).
# TABLES_TO_SKIP_CLEARING = []
TABLES_TO_SKIP_CLEARING = ["alembic_version"] # Example if using Alembic

# --- Helper Functions ---

def get_table_names(cursor):
    """Gets all user-defined table names from the database."""
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    return [row[0] for row in cursor.fetchall()]

def get_table_columns(cursor, table_name):
    """Gets column names for a given table."""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns_info = cursor.fetchall()
    if not columns_info:
        raise ValueError(f"Could not retrieve column info for table '{table_name}'. Does it exist?")
    # Return column names, handling potential variations in PRAGMA output across SQLite versions
    # Typically, the column name is the second item (index 1).
    return [col[1] for col in columns_info]


# --- Main Migration Logic ---

def migrate_data():
    """Migrates data from SOURCE_DB to DEST_DB."""
    if not os.path.exists(SOURCE_DB):
        logging.error(f"Source database '{SOURCE_DB}' not found. Aborting migration.")
        return

    if not os.path.exists(DEST_DB):
        logging.error(f"Destination database '{DEST_DB}' not found.")
        logging.error("Please ensure the destination database exists and has the correct schema.")
        logging.error("You might need to run the application once (using the new code) to initialize it.")
        return

    source_conn = None
    dest_conn = None

    try:
        logging.info(f"Connecting to source database: {SOURCE_DB}")
        source_conn = sqlite3.connect(SOURCE_DB)
        source_conn.row_factory = sqlite3.Row # Access columns by name
        source_cursor = source_conn.cursor()

        logging.info(f"Connecting to destination database: {DEST_DB}")
        dest_conn = sqlite3.connect(DEST_DB)
        dest_cursor = dest_conn.cursor()

        # Get tables from both databases
        source_tables = set(get_table_names(source_cursor))
        dest_tables = set(get_table_names(dest_cursor))
        common_tables = list(source_tables.intersection(dest_tables))

        logging.info(f"Found common tables to migrate: {', '.join(common_tables)}")

        if not common_tables:
            logging.warning("No common tables found between source and destination. Nothing to migrate.")
            return

        for table in common_tables:
            logging.info(f"--- Processing table: {table} ---")

            try:
                # Get column names from source (assuming schema matches or is compatible)
                columns = get_table_columns(source_cursor, table)
                column_names = ", ".join(f'"{c}"' for c in columns) # Quote names
                placeholders = ", ".join(["?"] * len(columns))

                # Clear destination table (optional, but safer for a clean migration)
                if table not in TABLES_TO_SKIP_CLEARING:
                    try:
                        logging.info(f"Clearing data from destination table: {table}")
                        dest_cursor.execute(f'DELETE FROM "{table}"') # Quote table name
                    except sqlite3.Error as e:
                        logging.error(f"Error clearing table {table} in destination: {e}. Skipping clear.")
                        # Decide whether to continue or abort for this table/all tables
                        # continue # Skip this table if clearing fails? Or proceed carefully?
                else:
                    logging.info(f"Skipping clear for table: {table}")


                # Fetch data from source
                logging.info(f"Fetching data from source table: {table}")
                source_cursor.execute(f'SELECT {column_names} FROM "{table}"') # Quote table name
                data_to_insert = source_cursor.fetchall()

                # Insert data into destination
                if data_to_insert:
                    logging.info(f"Inserting {len(data_to_insert)} rows into destination table: {table}")
                    try:
                        # Use INSERT OR IGNORE if you want to skip rows that violate constraints (e.g., duplicates)
                        # Use INSERT OR REPLACE if you want new rows to overwrite old ones based on primary key
                        # Default is INSERT, which will raise an error on constraint violation
                        sql_insert = f'INSERT INTO "{table}" ({column_names}) VALUES ({placeholders})'
                        dest_cursor.executemany(sql_insert, data_to_insert)
                    except sqlite3.IntegrityError as e:
                         logging.error(f"Integrity error inserting data into table {table}: {e}")
                         logging.warning("Consider using 'INSERT OR IGNORE' or 'INSERT OR REPLACE' if appropriate.")
                         logging.warning(f"Rolling back changes for table {table} due to integrity error.")
                         dest_conn.rollback() # Rollback changes for the current table on error
                         continue # Skip to next table
                    except sqlite3.Error as e:
                        logging.error(f"Error inserting data into table {table}: {e}")
                        dest_conn.rollback() # Rollback changes for the current table on error
                        logging.warning(f"Rolled back changes for table {table}")
                        continue # Skip to next table
                else:
                    logging.info(f"No data found in source table: {table}")

            except Exception as e:
                logging.error(f"Error processing table {table}: {e}", exc_info=True)
                logging.warning(f"Skipping table {table} due to error.")
                if dest_conn:
                    dest_conn.rollback() # Rollback any partial changes for this table

        # Commit changes to destination database
        logging.info("--- Committing final changes to destination database ---")
        dest_conn.commit()
        logging.info("Migration process finished.")

    except sqlite3.Error as e:
        logging.error(f"An SQLite error occurred during connection or setup: {e}")
        if dest_conn:
            dest_conn.rollback()
            logging.info("Rolled back any pending changes in destination database due to error.")
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}", exc_info=True)
        if dest_conn:
            dest_conn.rollback()
            logging.info("Rolled back any pending changes in destination database due to error.")
    finally:
        if source_conn:
            source_conn.close()
            logging.info("Closed source database connection.")
        if dest_conn:
            dest_conn.close()
            logging.info("Closed destination database connection.")

if __name__ == "__main__":
    migrate_data()