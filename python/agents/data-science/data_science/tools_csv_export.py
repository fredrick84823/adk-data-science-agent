# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""CSV export functionality for query results."""

import io
import uuid
from typing import Optional

import pandas as pd
from google.adk.tools import ToolContext
from google.genai import types


async def export_query_results_to_csv(
    tool_context: ToolContext,
    filename: Optional[str] = None,
) -> str:
    """Export the last query results to a CSV file.
    
    Args:
        filename (str, optional): Custom filename. If not provided, generates UUID-based name.
        
    Returns:
        str: Success message with download instructions.
    """
    # Check if query results exist
    if "query_result" not in tool_context.state:
        return "❌ No query results available to export. Please run a query first."
    
    query_result = tool_context.state["query_result"]
    
    if not query_result:
        return "❌ Query results are empty. Nothing to export."
    
    try:
        # Convert query results to DataFrame
        df = pd.DataFrame(query_result)
        
        # Generate filename if not provided
        if not filename:
            unique_id = str(uuid.uuid4())[:8]  # Use first 8 characters of UUID
            filename = f"agent-result-{unique_id}.csv"
        
        # Ensure filename has .csv extension
        if not filename.endswith('.csv'):
            filename += '.csv'
        
        # Create CSV content in memory
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        csv_content = csv_buffer.getvalue().encode('utf-8')
        
        # Save as artifact with display name
        csv_part = types.Part(
            inline_data=types.Blob(
                mimeType="text/csv",
                data=csv_content,
                displayName=filename
            )
        )
        await tool_context.save_artifact(
            filename=filename,
            artifact=csv_part
        )
        
        # Store export info in state for reference
        export_info = {
            "filename": filename,
            "rows": len(df),
            "columns": len(df.columns),
            "column_names": list(df.columns)
        }
        tool_context.state["last_csv_export"] = export_info
        
        # Return both text response and the artifact for display
        response_text = f"""✅ Query results exported successfully!

📊 **Export Details:**
- **Filename:** `{filename}`
- **Rows:** {len(df):,}
- **Columns:** {len(df.columns)}
- **Column Names:** {', '.join(df.columns)}

📥 **Download Instructions:**
The CSV file has been saved as an artifact. You can download it from the **Artifacts** section in the ADK web interface.

💡 **Tip:** The file contains all {len(df):,} rows from your query results in CSV format, ready for use in Excel, Google Sheets, or other data analysis tools."""
        
        # Also store the artifact for potential return
        tool_context.state["last_csv_artifact"] = csv_part
        
        return response_text
        
    except Exception as e:
        return f"❌ Error exporting query results to CSV: {str(e)}"


