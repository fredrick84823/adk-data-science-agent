#!/usr/bin/env python3
"""Test script to verify the SQL validation fix."""

import re

def test_sql_validation_fix():
    """Test that the new regex correctly identifies DML/DDL operations."""
    
    def contains_disallowed_operations(sql):
        """Check for disallowed SQL operations while avoiding false positives."""
        # Simple approach: remove string literals first, then check
        # This handles most common cases like LIKE '%create%'
        sql_without_strings = re.sub(r"'[^']*'", "", sql)  # Remove single-quoted strings
        sql_without_strings = re.sub(r'"[^"]*"', "", sql_without_strings)  # Remove double-quoted strings
        
        disallowed_pattern = r"(?i)\b(update|delete|drop|insert|create|alter|truncate|merge)\b"
        return re.search(disallowed_pattern, sql_without_strings)
    
    # Test cases
    test_cases = [
        # Should PASS (no false positives)
        {
            "sql": "SELECT t1.page_name, COUNT(t1.ad_archive_id) AS ad_count FROM `tagtoo-dxp.facebook_ad_library.ads` AS t1 WHERE t1.created_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY) GROUP BY t1.page_name ORDER BY ad_count DESC LIMIT 80",
            "should_fail": False,
            "description": "Original problematic query with CURRENT_TIMESTAMP"
        },
        {
            "sql": "SELECT * FROM table WHERE created_at > CURRENT_TIMESTAMP()",
            "should_fail": False,
            "description": "Simple SELECT with CURRENT_TIMESTAMP function"
        },
        {
            "sql": "SELECT recreate_field FROM table",
            "should_fail": False,
            "description": "Column name containing 'create'"
        },
        {
            "sql": "SELECT * FROM table WHERE description LIKE '%create%'",
            "should_fail": False,
            "description": "String literal containing 'create'"
        },
        
        # Should FAIL (actual DML/DDL operations)
        {
            "sql": "CREATE TABLE test (id INT)",
            "should_fail": True,
            "description": "CREATE TABLE statement"
        },
        {
            "sql": "INSERT INTO table VALUES (1, 2, 3)",
            "should_fail": True,
            "description": "INSERT statement"
        },
        {
            "sql": "UPDATE table SET column = value",
            "should_fail": True,
            "description": "UPDATE statement"
        },
        {
            "sql": "DELETE FROM table WHERE id = 1",
            "should_fail": True,
            "description": "DELETE statement"
        },
        {
            "sql": "DROP TABLE test",
            "should_fail": True,
            "description": "DROP statement"
        },
        {
            "sql": "ALTER TABLE test ADD COLUMN new_col INT",
            "should_fail": True,
            "description": "ALTER statement"
        }
    ]
    
    print("Testing SQL validation regex fix...")
    print("=" * 60)
    
    all_passed = True
    
    for i, test_case in enumerate(test_cases, 1):
        sql = test_case["sql"]
        should_fail = test_case["should_fail"]
        description = test_case["description"]
        
        match = contains_disallowed_operations(sql)
        is_detected_as_invalid = match is not None
        
        # Test passes if the detection matches expectation
        test_passed = is_detected_as_invalid == should_fail
        
        status = "✅ PASS" if test_passed else "❌ FAIL"
        if match:
            detected_op = match.group(1).upper()
            result_msg = f"Detected: {detected_op}"
        else:
            result_msg = "No disallowed operations detected"
        
        print(f"Test {i:2d}: {status}")
        print(f"  Description: {description}")
        print(f"  Expected: {'Should fail' if should_fail else 'Should pass'}")
        print(f"  Result: {result_msg}")
        print(f"  SQL: {sql[:80]}{'...' if len(sql) > 80 else ''}")
        print()
        
        if not test_passed:
            all_passed = False
    
    print("=" * 60)
    if all_passed:
        print("🎉 All tests PASSED! The validation fix is working correctly.")
    else:
        print("⚠️  Some tests FAILED. The fix may need further refinement.")
    
    return all_passed

if __name__ == "__main__":
    test_sql_validation_fix()