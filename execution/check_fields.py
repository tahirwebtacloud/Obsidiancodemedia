import os
import requests
from dotenv import load_dotenv

# Load env from root
dotenv_path = '.env'
load_dotenv(dotenv_path)

def check_fields():
    base_url = os.getenv("BASEROW_URL", "https://api.baserow.io")
    token = os.getenv("BASEROW_TOKEN")
    table_id = os.getenv("BASEROW_TABLE_ID_GENERATED_CONTENT")
    
    if not token or not table_id:
        print("Missing BASEROW_TOKEN or TABLE_ID in .env")
        return

    # API to get table fields
    url = f"{base_url}/api/database/fields/table/{table_id}/"
    headers = {"Authorization": f"Token {token}"}
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            fields = response.json()
            print(f"\n--- Fields for Table {table_id} ---")
            for field in fields:
                print(f"\nField: {field['name']} ({field['type']})")
                if 'select_options' in field:
                    print("Options:")
                    for opt in field['select_options']:
                        print(f"  - '{opt['value']}' (ID: {opt['id']})")
        else:
            print(f"Failed to fetch fields: {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_fields()
