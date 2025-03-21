#!/usr/bin/env python3
"""
Migration script to add UIDs to existing syllabi in the database.
This script:
1. Adds a unique ID (UUID) to each syllabus
2. Marks all existing syllabi as master versions
3. Sets parent_uid to null
4. Sets user_id to null
5. Adds created_at and updated_at timestamps
"""

import uuid
from datetime import datetime
import sys
from tinydb import TinyDB, Query

# Add the current directory to the path
sys.path.append(".")

def migrate_syllabi_to_uid_system():
    """Migrate existing syllabi to the new UID system."""
    print("Starting migration of syllabi to UID system...")
    
    # Open the database
    db = TinyDB("syllabus_db.json")
    syllabi_table = db.table("syllabi")
    
    # Get all existing syllabi
    all_syllabi = syllabi_table.all()
    print(f"Found {len(all_syllabi)} syllabi to migrate.")
    
    now = datetime.now().isoformat()
    migrated_count = 0
    
    # Update each syllabus
    for syllabus in all_syllabi:
        doc_id = syllabus.doc_id
        
        # Add UID if not present
        if "uid" not in syllabus:
            syllabus["uid"] = str(uuid.uuid4())
        
        # Mark as master version
        syllabus["is_master"] = True
        
        # Set user_id to None
        syllabus["user_id"] = None
        
        # Set parent_uid to None
        syllabus["parent_uid"] = None
        
        # Add timestamps
        if "created_at" not in syllabus:
            syllabus["created_at"] = now
        
        if "updated_at" not in syllabus:
            syllabus["updated_at"] = now
        
        # Update the syllabus in the database
        syllabi_table.update(syllabus, doc_ids=[doc_id])
        migrated_count += 1
    
    print(f"Migration complete. Updated {migrated_count} syllabi.")
    
    # Verify migration
    all_syllabi_after = syllabi_table.all()
    verified_count = 0
    
    for syllabus in all_syllabi_after:
        if (
            "uid" in syllabus
            and "is_master" in syllabus
            and "user_id" in syllabus
            and "parent_uid" in syllabus
            and "created_at" in syllabus
            and "updated_at" in syllabus
        ):
            verified_count += 1
    
    print(f"Verification complete. {verified_count}/{len(all_syllabi_after)} syllabi have all required fields.")

if __name__ == "__main__":
    migrate_syllabi_to_uid_system()