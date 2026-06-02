import os
import pandas as pd
import mysql.connector

# 1. List all the CSV files you want to import
csv_files = ["products.csv", "reorders.csv", "shipments.csv", "stock_entries.csv", "suppliers.csv"]

# 2. Connect to your MySQL Database (using your verified credentials)
conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="divyanshu",  
    database="project_back"
)
cursor = conn.cursor()

# Get the directory where this script is located (the 'db' folder)
script_dir = os.path.dirname(os.path.abspath(__file__))

print("Starting database ingestion pipeline...\n")

# 3. Loop through each file and import it from the new 'data' folder
for file_name in csv_files:
    # Build the path dynamically pointing directly into the 'data' subfolder
    file_path = os.path.join(script_dir, "data", file_name)
    
    # Check if the file actually exists before trying to read it
    if not os.path.exists(file_path):
        print(f"Skipping {file_name}: File not found at '{file_path}'.")
        continue
        
    # Get table name from file name (e.g., 'products.csv' -> 'products')
    table_name = os.path.splitext(file_name)[0]
    
    # Read and clean CSV column names to prevent SQL syntax spacing errors
    df = pd.read_csv(file_path)
    df.columns = [c.strip().lower().replace(' ', '_') for c in df.columns]
    
    # Dynamic Create Table Query
    columns_with_types = ", ".join([f"`{col}` TEXT" for col in df.columns])
    create_table_query = f"CREATE TABLE IF NOT EXISTS `{table_name}` ({columns_with_types});"
    
    print(f"Creating table '{table_name}' if it doesn't exist...")
    cursor.execute(create_table_query)
    
    # Dynamic Insert Query
    placeholders = ", ".join(["%s"] * len(df.columns))
    columns_joined = ", ".join([f"`{col}`" for col in df.columns])
    insert_query = f"INSERT INTO `{table_name}` ({columns_joined}) VALUES ({placeholders})"
    
    print(f"Importing data into '{table_name}'...")
    for _, row in df.iterrows():
        # Clean data fields (converts empty/NaN cells to None for proper MySQL NULL validation)
        row_values = [None if pd.isna(val) else val for val in row.values]
        cursor.execute(insert_query, row_values)
        
    print(f"-> Successfully imported {len(df)} rows into '{table_name}'!\n")

# Commit changes to database and wrap up cleanly
conn.commit()
cursor.close()
conn.close()

print("Database sync completed successfully! All data folders are up to date.")