# Syllabus UID System Test Plan

This document outlines the testing strategy for the syllabus UID system implementation.

## 1. Unit Tests

### 1.1 UID Generation Tests

- **Test UID Format**: Verify that generated UIDs follow UUID v4 format
- **Test UID Uniqueness**: Generate multiple UIDs and verify they are all unique

```python
def test_uid_generation():
    """Test that UIDs are generated correctly and uniquely."""
    import uuid
    
    # Generate multiple UIDs
    uids = [str(uuid.uuid4()) for _ in range(100)]
    
    # Check format (basic validation)
    for uid in uids:
        assert len(uid) == 36
        assert uid.count('-') == 4
    
    # Check uniqueness
    assert len(uids) == len(set(uids))
```

### 1.2 Master/User Version Logic Tests

- **Test Master Version Creation**: Verify that syllabi are correctly marked as master versions when no user_id is provided
- **Test User Version Creation**: Verify that syllabi are correctly marked as user versions when a user_id is provided
- **Test Parent Reference**: Verify that user versions correctly reference their parent master version

```python
def test_master_version_creation():
    """Test that syllabi are correctly marked as master versions when no user_id is provided."""
    # Create a test SyllabusAI instance
    syllabus_ai = SyllabusAI()
    syllabus_ai.initialize("Test Topic", "beginner")
    
    # Generate and save a syllabus
    syllabus = syllabus_ai.get_or_create_syllabus()
    syllabus_ai.save_syllabus()
    
    # Verify it's marked as a master version
    assert syllabus_ai.state["generated_syllabus"].get("is_master") is True
    assert syllabus_ai.state["generated_syllabus"].get("user_id") is None
    assert syllabus_ai.state["generated_syllabus"].get("parent_uid") is None

def test_user_version_creation():
    """Test that syllabi are correctly marked as user versions when a user_id is provided."""
    # Create a test SyllabusAI instance with a user_id
    user_id = "test_user_123"
    syllabus_ai = SyllabusAI()
    syllabus_ai.initialize("Test Topic", "beginner", user_id)
    
    # Generate and save a syllabus
    syllabus = syllabus_ai.get_or_create_syllabus()
    syllabus_ai.save_syllabus()
    
    # Verify it's marked as a user version
    assert syllabus_ai.state["generated_syllabus"].get("is_master") is False
    assert syllabus_ai.state["generated_syllabus"].get("user_id") == user_id
    assert syllabus_ai.state["generated_syllabus"].get("parent_uid") is not None
```

### 1.3 Syllabus Cloning Tests

- **Test Cloning from Master**: Verify that cloning a master syllabus creates a proper user version
- **Test Cloning from User Version**: Verify that cloning a user version maintains the correct parent reference

```python
def test_clone_from_master():
    """Test cloning a master syllabus for a specific user."""
    # Create a master syllabus
    syllabus_ai = SyllabusAI()
    syllabus_ai.initialize("Test Topic", "beginner")
    master_syllabus = syllabus_ai.get_or_create_syllabus()
    syllabus_ai.save_syllabus()
    
    # Clone it for a user
    user_id = "test_user_456"
    user_syllabus = syllabus_ai.clone_syllabus_for_user(user_id)
    
    # Verify the clone is a user version with the correct parent
    assert user_syllabus.get("is_master") is False
    assert user_syllabus.get("user_id") == user_id
    assert user_syllabus.get("parent_uid") == master_syllabus.get("uid")
```

## 2. Integration Tests

### 2.1 Full Workflow Tests

- **Test Create-Retrieve-Update Cycle**: Verify the complete workflow with user IDs
- **Test Multiple Users**: Verify that multiple users can have different versions of the same syllabus

```python
def test_create_retrieve_update_cycle():
    """Test the complete workflow with user IDs."""
    user_id = "test_user_789"
    topic = "Integration Test Topic"
    level = "beginner"
    
    # Create a syllabus for a user
    syllabus_ai_1 = SyllabusAI()
    syllabus_ai_1.initialize(topic, level, user_id)
    syllabus_1 = syllabus_ai_1.get_or_create_syllabus()
    syllabus_ai_1.save_syllabus()
    
    # Retrieve the same syllabus
    syllabus_ai_2 = SyllabusAI()
    syllabus_ai_2.initialize(topic, level, user_id)
    syllabus_2 = syllabus_ai_2.get_or_create_syllabus()
    
    # Verify it's the same syllabus
    assert syllabus_2.get("uid") == syllabus_1.get("uid")
    
    # Update the syllabus
    feedback = "Please add more content to week 2"
    updated_syllabus = syllabus_ai_2.update_syllabus(feedback)
    syllabus_ai_2.save_syllabus()
    
    # Retrieve it again
    syllabus_ai_3 = SyllabusAI()
    syllabus_ai_3.initialize(topic, level, user_id)
    syllabus_3 = syllabus_ai_3.get_or_create_syllabus()
    
    # Verify it's the updated version
    assert syllabus_3.get("uid") == syllabus_1.get("uid")
    assert syllabus_3.get("updated_at") != syllabus_1.get("updated_at")
```

### 2.2 User-Specific Retrieval Tests

- **Test User-Specific Retrieval**: Verify that user-specific versions are retrieved when available
- **Test Fallback to Master**: Verify that master versions are retrieved when no user-specific version exists

```python
def test_user_specific_retrieval():
    """Test that user-specific versions are retrieved when available."""
    topic = "Retrieval Test Topic"
    level = "beginner"
    user_id_1 = "test_user_a"
    user_id_2 = "test_user_b"
    
    # Create a syllabus for user 1
    syllabus_ai_1 = SyllabusAI()
    syllabus_ai_1.initialize(topic, level, user_id_1)
    syllabus_1 = syllabus_ai_1.get_or_create_syllabus()
    syllabus_ai_1.save_syllabus()
    
    # Create a syllabus for user 2
    syllabus_ai_2 = SyllabusAI()
    syllabus_ai_2.initialize(topic, level, user_id_2)
    syllabus_2 = syllabus_ai_2.get_or_create_syllabus()
    syllabus_ai_2.save_syllabus()
    
    # Verify they have different UIDs but the same parent
    assert syllabus_1.get("uid") != syllabus_2.get("uid")
    assert syllabus_1.get("parent_uid") == syllabus_2.get("parent_uid")
    
    # Retrieve for user 1 again
    syllabus_ai_3 = SyllabusAI()
    syllabus_ai_3.initialize(topic, level, user_id_1)
    syllabus_3 = syllabus_ai_3.get_or_create_syllabus()
    
    # Verify it's user 1's version
    assert syllabus_3.get("uid") == syllabus_1.get("uid")
```

### 2.3 Fallback Tests

```python
def test_fallback_to_master():
    """Test that master versions are retrieved when no user-specific version exists."""
    topic = "Fallback Test Topic"
    level = "beginner"
    
    # Create a master syllabus
    syllabus_ai_1 = SyllabusAI()
    syllabus_ai_1.initialize(topic, level)
    syllabus_1 = syllabus_ai_1.get_or_create_syllabus()
    syllabus_ai_1.save_syllabus()
    
    # Retrieve for a user that doesn't have a specific version
    user_id = "new_test_user"
    syllabus_ai_2 = SyllabusAI()
    syllabus_ai_2.initialize(topic, level, user_id)
    syllabus_2 = syllabus_ai_2.get_or_create_syllabus()
    
    # Verify it's the master version
    assert syllabus_2.get("uid") == syllabus_1.get("uid")
    assert syllabus_2.get("is_master") is True
```

## 3. Migration Tests

### 3.1 Migration Script Tests

- **Test Migration on Sample Data**: Verify the migration script works correctly on a sample database
- **Test Migration Idempotence**: Verify that running the migration script multiple times doesn't cause issues

```python
def test_migration_on_sample_data():
    """Test the migration script on a sample database."""
    import tempfile
    import os
    import json
    from tinydb import TinyDB
    
    # Create a temporary database with sample data
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_db_path = temp_file.name
    
    db = TinyDB(temp_db_path)
    syllabi_table = db.table("syllabi")
    
    # Add sample syllabi without UIDs
    sample_syllabi = [
        {
            "topic": "Sample Topic 1",
            "level": "Beginner",
            "duration": "4 weeks",
            "learning_objectives": ["Objective 1", "Objective 2"],
            "modules": [
                {
                    "week": 1,
                    "title": "Module 1",
                    "lessons": [{"title": "Lesson 1"}, {"title": "Lesson 2"}]
                }
            ]
        },
        {
            "topic": "Sample Topic 2",
            "level": "Advanced",
            "duration": "6 weeks",
            "learning_objectives": ["Objective 1", "Objective 2"],
            "modules": [
                {
                    "week": 1,
                    "title": "Module 1",
                    "lessons": [{"title": "Lesson 1"}, {"title": "Lesson 2"}]
                }
            ]
        }
    ]
    
    for syllabus in sample_syllabi:
        syllabi_table.insert(syllabus)
    
    # Run the migration script
    from migrate_syllabi_to_uid import migrate_syllabi_to_uid_system
    migrate_syllabi_to_uid_system(db_path=temp_db_path)
    
    # Verify the migration
    db = TinyDB(temp_db_path)
    syllabi_table = db.table("syllabi")
    migrated_syllabi = syllabi_table.all()
    
    for syllabus in migrated_syllabi:
        assert "uid" in syllabus
        assert "is_master" in syllabus and syllabus["is_master"] is True
        assert "user_id" in syllabus and syllabus["user_id"] is None
        assert "parent_uid" in syllabus and syllabus["parent_uid"] is None
        assert "created_at" in syllabus
        assert "updated_at" in syllabus
    
    # Clean up
    os.unlink(temp_db_path)
```

## 4. UI Tests

### 4.1 Streamlit App Tests

- **Test User ID Generation**: Verify that temporary user IDs are generated correctly
- **Test Version Display**: Verify that version information is displayed correctly
- **Test User-Specific Workflow**: Verify the complete user workflow in the UI

These tests would be performed manually or with a UI testing framework like Selenium.

## 5. Performance Tests

### 5.1 Database Performance

- **Test Large Database**: Verify performance with a large number of syllabi
- **Test Multiple Users**: Verify performance with many users accessing the same syllabus topic

```python
def test_large_database_performance():
    """Test performance with a large number of syllabi."""
    import time
    import tempfile
    import os
    from tinydb import TinyDB
    
    # Create a temporary database
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_db_path = temp_file.name
    
    db = TinyDB(temp_db_path)
    syllabi_table = db.table("syllabi")
    
    # Add a large number of syllabi
    for i in range(1000):
        syllabi_table.insert({
            "uid": f"test-uid-{i}",
            "topic": f"Performance Test Topic {i}",
            "level": "Beginner",
            "is_master": True,
            "user_id": None,
            "parent_uid": None,
            "created_at": "2023-01-01T00:00:00",
            "updated_at": "2023-01-01T00:00:00"
        })
    
    # Test search performance
    start_time = time.time()
    
    syllabus_query = Query()
    for i in range(100):
        syllabi_table.search(
            (syllabus_query.topic == f"Performance Test Topic {i}")
            & (syllabus_query.is_master == True)
        )
    
    end_time = time.time()
    search_time = end_time - start_time
    
    print(f"Time to perform 100 searches: {search_time:.2f} seconds")
    assert search_time < 5.0  # Should be reasonably fast
    
    # Clean up
    os.unlink(temp_db_path)
```

## 6. Security Tests

### 6.1 User ID Validation

- **Test User ID Validation**: Verify that user IDs are properly validated
- **Test Access Control**: Verify that users can only access their own syllabi or master versions

```python
def test_user_id_validation():
    """Test that user IDs are properly validated."""
    # Test with various invalid user IDs
    invalid_user_ids = [
        None,
        "",
        " ",
        "<script>alert('XSS')</script>",
        "user;DROP TABLE syllabi;"
    ]
    
    for invalid_id in invalid_user_ids:
        try:
            syllabus_ai = SyllabusAI()
            syllabus_ai.initialize("Test Topic", "beginner", invalid_id)
            # If we get here with certain invalid IDs, make sure they're handled properly
            if invalid_id in (None, "", " "):
                assert syllabus_ai.state.get("user_id") is None
            else:
                # For potentially malicious IDs, they should be sanitized or rejected
                assert syllabus_ai.state.get("user_id") != invalid_id
        except ValueError:
            # Some invalid IDs might raise exceptions, which is also acceptable
            pass
```

## 7. Regression Tests

- **Test Existing Functionality**: Verify that all existing functionality continues to work with the UID system
- **Test Backward Compatibility**: Verify that the system can still work with old data formats if needed

These tests would ensure that the new UID system doesn't break any existing functionality.