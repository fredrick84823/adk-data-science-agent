#!/usr/bin/env python3
"""Test script for CSV export functionality."""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from data_science.tools_csv_export import export_query_results_to_csv
from google.adk.tools import ToolContext

# Mock ToolContext for testing
class MockToolContext:
    def __init__(self):
        self.state = {}
        self.saved_artifacts = []
    
    async def save_artifact(self, filename, artifact):
        # Extract content from the artifact for testing
        if hasattr(artifact, 'inline_data') and artifact.inline_data:
            content = artifact.inline_data.data
            content_type = artifact.inline_data.mime_type
        else:
            content = b"mock content"
            content_type = "application/octet-stream"
            
        self.saved_artifacts.append({
            'filename': filename,
            'content': content,
            'content_type': content_type,
            'size': len(content)
        })
        print(f"✅ Artifact saved: {filename} ({len(content)} bytes, {content_type})")
        return 1  # Return artifact ID

async def test_csv_export():
    """Test CSV export functionality."""
    print("🧪 Testing CSV Export Functionality\n")
    
    # Test 1: No query results
    print("Test 1: No query results available")
    tool_context = MockToolContext()
    result = await export_query_results_to_csv(tool_context)
    print(f"Result: {result}\n")
    
    # Test 2: Empty query results
    print("Test 2: Empty query results")
    tool_context = MockToolContext()
    tool_context.state["query_result"] = []
    result = await export_query_results_to_csv(tool_context)
    print(f"Result: {result}\n")
    
    # Test 3: Valid query results
    print("Test 3: Valid query results")
    tool_context = MockToolContext()
    tool_context.state["query_result"] = [
        {"name": "Alice", "age": 30, "city": "New York"},
        {"name": "Bob", "age": 25, "city": "San Francisco"},
        {"name": "Charlie", "age": 35, "city": "Chicago"}
    ]
    result = await export_query_results_to_csv(tool_context)
    print(f"Result: {result}\n")
    
    # Check if artifact was saved
    if tool_context.saved_artifacts:
        artifact = tool_context.saved_artifacts[0]
        print(f"📁 Saved artifact details:")
        print(f"   - Filename: {artifact['filename']}")
        print(f"   - Content Type: {artifact['content_type']}")
        print(f"   - Size: {artifact['size']} bytes")
        print(f"   - Content preview: {artifact['content'][:100].decode('utf-8')}...")
    
    # Test 4: Custom filename
    print("\nTest 4: Custom filename")
    tool_context = MockToolContext()
    tool_context.state["query_result"] = [{"test": "data"}]
    result = await export_query_results_to_csv(tool_context, "my-custom-export")
    print(f"Result: {result}\n")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_csv_export())