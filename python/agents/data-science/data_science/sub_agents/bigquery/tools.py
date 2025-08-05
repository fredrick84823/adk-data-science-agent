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

"""This file contains the tools used by the database agent."""

import datetime
import json
import logging
import os
import re

import numpy as np
import pandas as pd
from data_science.utils.utils import get_env_var
from google.adk.tools import ToolContext
from google.cloud import bigquery
from google.genai import Client

from .chase_sql import chase_constants

# Assume that `BQ_COMPUTE_PROJECT_ID` and `BQ_DATA_PROJECT_ID` are set in the
# environment. See the `data_agent` README for more details.
data_project = os.getenv("BQ_DATA_PROJECT_ID", None)
compute_project = os.getenv("BQ_COMPUTE_PROJECT_ID", None)
vertex_project = os.getenv("GOOGLE_CLOUD_PROJECT", None)
location = os.getenv("GOOGLE_CLOUD_LOCATION", "asia-east1")
use_vertexai = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "0") == "1"
llm_client = Client(vertexai=use_vertexai, project=vertex_project, location=location)

MAX_NUM_ROWS = 80

def get_multi_project_config():
    """Get multi-project configuration from environment."""
    config_str = os.getenv("BQ_MULTI_PROJECT_CONFIG", "{}")
    try:
        return json.loads(config_str)
    except json.JSONDecodeError as e:
        logging.warning(f"Invalid BQ_MULTI_PROJECT_CONFIG format: {e}")
        # Fallback to single project mode
        data_project = os.getenv("BQ_DATA_PROJECT_ID")
        dataset_id = os.getenv("BQ_DATASET_ID", "").strip("'\"")
        if data_project and dataset_id:
            return {data_project: [dataset_id]}
        return {}


def get_all_projects_and_datasets():
    """Get all configured projects and their datasets."""
    config = get_multi_project_config()
    all_mappings = []
    for project_id, datasets in config.items():
        for dataset_id in datasets:
            all_mappings.append((project_id, dataset_id))
    return all_mappings


def _serialize_value_for_sql(value):
    """Serializes a Python value from a pandas DataFrame into a BigQuery SQL literal."""
    if pd.isna(value):
        return "NULL"
    if isinstance(value, str):
        # Escape single quotes and backslashes for SQL strings.
        escaped = value.replace('\\', '\\\\')
        escaped = escaped.replace("'", "''")
        return f"'{escaped}'"
    if isinstance(value, bytes):
        decoded = value.decode('utf-8', 'replace')
        decoded = decoded.replace('\\', '\\\\')
        decoded = decoded.replace("'", "''")
        return f"b'{decoded}'"
    if isinstance(value, (datetime.datetime, datetime.date, pd.Timestamp)):
        # Timestamps and datetimes need to be quoted.
        return f"'{value}'"
    if isinstance(value, (list, np.ndarray)):
        # Format arrays.
        return f"[{', '.join(_serialize_value_for_sql(v) for v in value)}]"
    if isinstance(value, dict):
        # For STRUCT, BQ expects ('val1', 'val2', ...).
        # The values() order from the dataframe should match the column order.
        return f"({', '.join(_serialize_value_for_sql(v) for v in value.values())})"
    return str(value)


database_settings = None
bq_client = None


def get_bq_client(project_id=None):
    """Get BigQuery client for a specific project.
    
    Args:
        project_id (str, optional): Specific project ID. If None, uses default compute project.
    
    Returns:
        bigquery.Client: BigQuery client instance
    """
    global bq_client
    
    # Use provided project or default compute project
    target_project = project_id or get_env_var("BQ_COMPUTE_PROJECT_ID")
    
    # Create client with service account if configured
    from ...utils.utils import get_credentials_path
    credentials_path = get_credentials_path()
    if credentials_path and os.path.exists(credentials_path):
        from google.oauth2 import service_account
        credentials = service_account.Credentials.from_service_account_file(credentials_path)
        return bigquery.Client(
            project=target_project,
            location=location,
            credentials=credentials
        )
    else:
        # Fallback to default credentials (for backward compatibility)
        if bq_client is None or (project_id and bq_client.project != target_project):
            bq_client = bigquery.Client(
                project=target_project,
                location=location
            )
        return bq_client


def get_database_settings():
    """Get database settings for all configured projects and datasets."""
    global database_settings
    if database_settings is None:
        database_settings = update_database_settings()
    return database_settings


def update_database_settings():
    """Update database settings to include all configured projects and datasets."""
    global database_settings
    
    # Get all project-dataset pairs
    all_mappings = get_all_projects_and_datasets()
    
    if not all_mappings:
        # Fallback to single project mode for backward compatibility
        ddl_schema = get_bigquery_schema(
            dataset_id=get_env_var("BQ_DATASET_ID").strip("'\""),
            data_project_id=get_env_var("BQ_DATA_PROJECT_ID"),
            client=get_bq_client(),
            compute_project_id=get_env_var("BQ_COMPUTE_PROJECT_ID")
        )
        database_settings = {
            "bq_project_id": get_env_var("BQ_DATA_PROJECT_ID"),
            "bq_dataset_id": get_env_var("BQ_DATASET_ID"),
            "bq_ddl_schema": ddl_schema,
            **chase_constants.chase_sql_constants_dict,
        }
    else:
        # Multi-project mode
        all_schemas = []
        project_info = []
        
        for data_project_id, dataset_id in all_mappings:
            try:
                compute_project_id = get_env_var("BQ_COMPUTE_PROJECT_ID")
                client = get_bq_client(compute_project_id)
                
                schema = get_bigquery_schema(
                    dataset_id=dataset_id,
                    data_project_id=data_project_id,
                    client=client,
                    compute_project_id=compute_project_id
                )
                
                all_schemas.append(f"\n--- Project: {data_project_id}, Dataset: {dataset_id} ---\n{schema}")
                project_info.append({"project": data_project_id, "dataset": dataset_id})
                
            except Exception as e:
                logging.warning(f"Failed to get schema for {data_project_id}.{dataset_id}: {e}")
        
        combined_schema = "\n".join(all_schemas)
        
        database_settings = {
            "bq_multi_project": True,
            "bq_project_datasets": project_info,
            "bq_ddl_schema": combined_schema,
            **chase_constants.chase_sql_constants_dict,
        }
    
    return database_settings


def get_bigquery_schema(dataset_id,
                        data_project_id,
                        client=None,
                        compute_project_id=None):
    """Retrieves schema and generates DDL with example values for a BigQuery dataset.

    Args:
        dataset_id (str): The ID of the BigQuery dataset (e.g., 'my_dataset').
        data_project_id (str): Project used for BQ data.
        client (bigquery.Client): A BigQuery client.
        compute_project_id (str): Project used for BQ compute.

    Returns:
        str: A string containing the generated DDL statements.
    """

    if client is None:
        client = get_bq_client(compute_project_id)

    # dataset_ref = client.dataset(dataset_id)
    dataset_ref = bigquery.DatasetReference(data_project_id, dataset_id)

    ddl_statements = ""

    # Query INFORMATION_SCHEMA to robustly list tables. This is the recommended
    # approach when a dataset may contain BigLake tables like Apache Iceberg,
    # as the tables.list API can fail in those cases.
    info_schema_query = f"""
        SELECT table_name
        FROM `{data_project_id}.{dataset_id}.INFORMATION_SCHEMA.TABLES`
    """
    query_job = client.query(info_schema_query)

    for table_row in query_job.result():
        table_ref = dataset_ref.table(table_row.table_name)
        table_obj = client.get_table(table_ref)

        if table_obj.table_type == "VIEW":
            view_query = table_obj.view_query
            ddl_statements += (
                f"CREATE OR REPLACE VIEW `{table_ref}` AS\n{view_query};\n\n"
            )
            continue
        elif table_obj.table_type == "EXTERNAL":
            if (
                table_obj.external_data_configuration
                and table_obj.external_data_configuration.source_format
                == "ICEBERG"
            ):
                config = table_obj.external_data_configuration
                uris_list_str = ",\n    ".join(
                    [f"'{uri}'" for uri in config.source_uris]
                )

                # Build column definitions from schema
                column_defs = []
                for field in table_obj.schema:
                    col_type = field.field_type
                    if field.mode == "REPEATED":
                        col_type = f"ARRAY<{col_type}>"
                    column_defs.append(f"  `{field.name}` {col_type}")
                columns_str = ",\n".join(column_defs)

                ddl_statements += f"""CREATE EXTERNAL TABLE `{table_ref}` (
{columns_str}
)
WITH CONNECTION `{config.connection_id}`
OPTIONS (
  uris = [{uris_list_str}],
  format = 'ICEBERG'
);\n\n"""
            # Skip DDL generation for other external tables.
            continue
        elif table_obj.table_type == "TABLE":
            column_defs = []
            for field in table_obj.schema:
                col_type = field.field_type
                if field.mode == "REPEATED":
                    col_type = f"ARRAY<{col_type}>"
                col_def = f"  `{field.name}` {col_type}"
                if field.description:
                    # Use OPTIONS for column descriptions
                    col_def += (
                        " OPTIONS(description='"
                        f"{field.description.replace("'", "''")}')"
                    )
                column_defs.append(col_def)

            ddl_statement = (
                f"CREATE OR REPLACE TABLE `{table_ref}` "
                f"(\n{',\n'.join(column_defs)}\n);\n\n"
            )

            # Add example values if available by running a query. This is more
            # robust than list_rows, especially for BigLake tables like Iceberg.
            try:
                sample_query = f"SELECT * FROM `{table_ref}` LIMIT 5"
                rows = client.query(sample_query).to_dataframe()

                if not rows.empty:
                    ddl_statement += f"-- Example values for table `{table_ref}`:\n"
                    for _, row in rows.iterrows():
                        values_str = ", ".join(
                            _serialize_value_for_sql(v) for v in row.values
                        )
                        ddl_statement += (
                            f"INSERT INTO `{table_ref}` VALUES ({values_str});\n\n"
                        )
            except Exception as e:
                logging.warning(
                    f"Could not retrieve sample rows for table {table_ref.path}: {e}"
                )
                ddl_statement += f"-- NOTE: Could not retrieve sample rows for table {table_ref.path}.\n\n"

            ddl_statements += ddl_statement
        else:
            # Skip other types like MATERIALIZED_VIEW, SNAPSHOT etc.
            continue

    return ddl_statements


def initial_bq_nl2sql(
    question: str,
    tool_context: ToolContext,
) -> str:
    """Generates an initial SQL query from a natural language question.

    Args:
        question (str): Natural language question.
        tool_context (ToolContext): The tool context to use for generating the SQL
          query.

    Returns:
        str: An SQL statement to answer this question.
    """

    prompt_template = """
You are a BigQuery SQL expert tasked with answering user's questions about BigQuery tables by generating SQL queries in the GoogleSql dialect. You have access to multiple BigQuery projects and datasets. Your task is to write a BigQuery SQL query that answers the following question while using the provided context.

**Guidelines:**

- **Multi-Project Access:** You have access to multiple BigQuery projects and datasets. Always use the full table name with the complete project.dataset.table format.
- **Table Referencing:** Always use the full table name with the database prefix in the SQL statement. Tables should be referred to using a fully qualified name enclosed in backticks (`) e.g. `project_name.dataset_name.table_name`. Table names are case sensitive.
- **Cross-Project Queries:** You can join tables across different projects. Always specify the full project.dataset.table path for each table.
- **Joins:** Join as few tables as possible. When joining tables, ensure all join columns are the same data type. Analyze the database and the table schema provided to understand the relationships between columns and tables.
- **Aggregations:** Use all non-aggregated columns from the `SELECT` statement in the `GROUP BY` clause.
- **SQL Syntax:** Return syntactically and semantically correct SQL for BigQuery with proper relation mapping (i.e., project_id, owner, table, and column relation). Use SQL `AS` statement to assign a new name temporarily to a table column or even a table wherever needed. Always enclose subqueries and union queries in parentheses.
- **Column Usage:** Use *ONLY* the column names (column_name) mentioned in the Table Schema. Do *NOT* use any other column names. Associate `column_name` mentioned in the Table Schema only to the `table_name` specified under Table Schema.
- **FILTERS:** You should write queries effectively to reduce and minimize the total rows to be returned. For example, you can use filters (like `WHERE`, `HAVING`, etc.) in the SQL query.
- **LIMIT ROWS:** The maximum number of rows returned should be less than {MAX_NUM_ROWS}.

**Available Projects and Datasets:**

The database structure is defined by the following table schemas from multiple projects (possibly with sample rows):

```
{SCHEMA}
```

**Natural language question:**

```
{QUESTION}
```

**Think Step-by-Step:** Carefully consider the schema from all available projects, the question, guidelines, and best practices outlined above to generate the correct BigQuery SQL. Remember that you can access tables from any of the listed projects and datasets.

   """

    ddl_schema = tool_context.state["database_settings"]["bq_ddl_schema"]

    prompt = prompt_template.format(
        MAX_NUM_ROWS=MAX_NUM_ROWS, SCHEMA=ddl_schema, QUESTION=question
    )

    response = llm_client.models.generate_content(
        model=os.getenv("BASELINE_NL2SQL_MODEL"),
        contents=prompt,
        config={"temperature": 0.1},
    )

    sql = response.text
    if sql:
        sql = sql.replace("```sql", "").replace("```", "").strip()

    print("\n sql:", sql)

    tool_context.state["sql_query"] = sql

    return sql


def run_bigquery_validation(
    sql_string: str,
    tool_context: ToolContext,
) -> str:
    """Validates BigQuery SQL syntax and functionality.

    This function validates the provided SQL string by attempting to execute it
    against BigQuery in dry-run mode. It performs the following checks:

    1. **SQL Cleanup:**  Preprocesses the SQL string using a `cleanup_sql`
    function
    2. **DML/DDL Restriction:**  Rejects any SQL queries containing DML or DDL
       statements (e.g., UPDATE, DELETE, INSERT, CREATE, ALTER) to ensure
       read-only operations.
    3. **Syntax and Execution:** Sends the cleaned SQL to BigQuery for validation.
       If the query is syntactically correct and executable, it retrieves the
       results.
    4. **Result Analysis:**  Checks if the query produced any results. If so, it
       formats the first few rows of the result set for inspection.

    Args:
        sql_string (str): The SQL query string to validate.
        tool_context (ToolContext): The tool context to use for validation.

    Returns:
        str: A message indicating the validation outcome. This includes:
             - "Valid SQL. Results: ..." if the query is valid and returns data.
             - "Valid SQL. Query executed successfully (no results)." if the query
                is valid but returns no data.
             - "Invalid SQL: ..." if the query is invalid, along with the error
                message from BigQuery.
    """

    def cleanup_sql(sql_string):
        """Processes the SQL string to get a printable, valid SQL string."""

        # 1. Remove backslashes escaping double quotes
        sql_string = sql_string.replace('\\"', '"')

        # 2. Remove backslashes before newlines (the key fix for this issue)
        sql_string = sql_string.replace("\\\n", "\n")  # Corrected regex

        # 3. Replace escaped single quotes
        sql_string = sql_string.replace("\\'", "'")

        # 4. Replace escaped newlines (those not preceded by a backslash)
        sql_string = sql_string.replace("\\n", "\n")

        # 5. Add limit clause if not present
        if "limit" not in sql_string.lower():
            sql_string = sql_string + " limit " + str(MAX_NUM_ROWS)

        return sql_string

    logging.info("Validating SQL: %s", sql_string)
    sql_string = cleanup_sql(sql_string)
    logging.info("Validating SQL (after cleanup): %s", sql_string)

    final_result = {"query_result": None, "error_message": None}

    # More restrictive check for BigQuery - disallow DML and DDL
    # Use word boundaries (\b) to match whole words only, not substrings
    # Also exclude matches inside string literals (basic approach)
    def contains_disallowed_operations(sql):
        """Check for disallowed SQL operations while avoiding false positives."""
        # Simple approach: remove string literals first, then check
        # This handles most common cases like LIKE '%create%'
        sql_without_strings = re.sub(r"'[^']*'", "", sql)  # Remove single-quoted strings
        sql_without_strings = re.sub(r'"[^"]*"', "", sql_without_strings)  # Remove double-quoted strings
        
        disallowed_pattern = r"(?i)\b(update|delete|drop|insert|create|alter|truncate|merge)\b"
        return re.search(disallowed_pattern, sql_without_strings)
    
    disallowed_match = contains_disallowed_operations(sql_string)
    if disallowed_match:
        matched_operation = disallowed_match.group(1)
        final_result["error_message"] = (
            f"Invalid SQL: Contains disallowed DML/DDL operation: {matched_operation.upper()}"
        )
        logging.warning("SQL validation failed - disallowed operation '%s' found in: %s", 
                       matched_operation, sql_string[:200] + "..." if len(sql_string) > 200 else sql_string)
        return final_result

    try:
        # Determine which project to use for the query execution
        # For cross-project queries, use the compute project
        compute_project_id = get_env_var("BQ_COMPUTE_PROJECT_ID")
        query_job = get_bq_client(compute_project_id).query(sql_string)
        results = query_job.result()  # Get the query results

        if results.schema:  # Check if query returned data
            rows = [
                {
                    key: (
                        value
                        if not isinstance(value, datetime.date)
                        else value.strftime("%Y-%m-%d")
                    )
                    for (key, value) in row.items()
                }
                for row in results
            ][
                :MAX_NUM_ROWS
            ]  # Convert BigQuery RowIterator to list of dicts
            # return f"Valid SQL. Results: {rows}"
            final_result["query_result"] = rows

            tool_context.state["query_result"] = rows

        else:
            final_result["error_message"] = (
                "Valid SQL. Query executed successfully (no results)."
            )

    except (
        Exception
    ) as e:  # Catch generic exceptions from BigQuery  # pylint: disable=broad-exception-caught
        final_result["error_message"] = f"Invalid SQL: {e}"

    print("\n run_bigquery_validation final_result: \n", final_result)

    return final_result
