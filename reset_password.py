# reset_password.py
"""CLI script to reset user password"""
import argparse
import getpass
import sqlite3
import sys
from pathlib import Path

import bcrypt

# Define the database path relative to the script's location or project root
# Assuming the script is run from the project root directory
DB_NAME = "techtree_db.sqlite"
DB_PATH = Path(__file__).parent / DB_NAME


def hash_password(password: str) -> str:
    """Hash a password for storing using bcrypt."""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def reset_user_password(email: str, new_user_password: str):
    """Finds a user by email and updates their password hash in the database."""
    conn = None
    try:
        if not DB_PATH.exists():
            print(f"Error: Database file not found at {DB_PATH}")
            sys.exit(1)

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Check if user exists
        cursor.execute("SELECT user_id FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()

        if not user:
            print(f"Error: User with email '{email}' not found.")
            return False

        user_id = user[0]
        print(f"Found user: {email} (ID: {user_id})")

        # Hash the new password
        new_password_hash = hash_password(new_user_password)
        print("New password hashed.")

        # Update the password hash in the database
        cursor.execute(
            "UPDATE users SET password_hash = ? WHERE user_id = ?",
            (new_password_hash, user_id),
        )
        conn.commit()

        if cursor.rowcount > 0:
            print(f"Successfully updated password for user '{email}'.")
            return True
        else:
            # Should not happen if user was found, but good to check
            print(
                f"Error: Failed to update password for user '{email}'. No rows affected."
            )
            return False

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        if conn:
            conn.rollback()
        return False
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()
            print("Database connection closed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Reset a user's password in the Tech Tree database."
    )
    parser.add_argument(
        "email", help="The email address of the user whose password needs resetting."
    )
    args = parser.parse_args()

    print(f"Attempting to reset password for user: {args.email}")

    # Prompt securely for the new password
    new_password = getpass.getpass(f"Enter new password for {args.email}: ")
    confirm_password = getpass.getpass("Confirm new password: ")

    if new_password != confirm_password:
        print("Error: Passwords do not match.")
        sys.exit(1)

    if not new_password:
        print("Error: Password cannot be empty.")
        sys.exit(1)

    reset_user_password(args.email, new_password)
