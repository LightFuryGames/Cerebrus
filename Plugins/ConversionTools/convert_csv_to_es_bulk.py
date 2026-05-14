import csv
import json
import sys
import os
import re
from datetime import datetime

def parse_value(v):
    if v is None or v.strip() == '':
        return None
    try:
        # Check if it's an integer
        if '.' not in v and 'e' not in v.lower():
            return int(v)
        return float(v)
    except ValueError:
        return v

def convert(csv_filepath, index_name="unreal-profiling"):
    json_filepath = os.path.splitext(csv_filepath)[0] + "_bulk.json"
    
    # Try to extract timestamp from filename like Profile(20260326_171116).csv
    # This helps Grafana plot the data temporally
    file_timestamp = None
    match = re.search(r'\((\d{8}_\d{6})\)', os.path.basename(csv_filepath))
    if match:
        try:
            # Parse '20260326_171116' to ISO 8601
            dt = datetime.strptime(match.group(1), "%Y%m%d_%H%M%S")
            file_timestamp = dt.isoformat() + "Z"
        except Exception:
            pass

    with open(csv_filepath, 'r', encoding='utf-8-sig') as f_in:
        lines = f_in.readlines()
        
    metadata = {}
    if lines and "[HasHeaderRowAtEnd]" in lines[-1]:
        # Parse the metadata from the last line
        last_line = lines.pop().strip()
        # Parse as CSV to handle quoted strings
        last_row = next(csv.reader([last_line]))
        for i in range(0, len(last_row), 2):
            if i + 1 < len(last_row):
                key = last_row[i].strip('[]')
                value = parse_value(last_row[i+1])
                metadata[key] = value
                
        # Remove the duplicated header row if it exists at the end
        if lines and "EVENTS" in lines[-1]:
            lines.pop()

    with open(json_filepath, 'w', encoding='utf-8') as f_out:
        if metadata:
            if file_timestamp:
                metadata['@timestamp'] = file_timestamp
            metadata['event_type'] = 'metadata'
            action = {"index": {"_index": index_name}}
            f_out.write(json.dumps(action) + "\n")
            f_out.write(json.dumps(metadata) + "\n")
            
        reader = csv.DictReader(lines)
        
        # Add a frame counter as a simple way to sequence events
        frame_number = 0
        
        for row in reader:
            # Build the document
            doc = {}
            if file_timestamp:
                doc['@timestamp'] = file_timestamp
            doc['frame_number'] = frame_number
            doc['event_type'] = 'frame_data'
            
            for key, value in row.items():
                if key is None or key.strip() == '':
                    continue
                # Sanitize keys for ES (replace slashes with underscores)
                # This prevents ES from misinterpreting slashes or causing query issues
                clean_key = key.replace('/', '_')
                doc[clean_key] = parse_value(value)
                
            # Write Elasticsearch bulk API action and metadata
            action = {"index": {"_index": index_name}}
            f_out.write(json.dumps(action) + "\n")
            f_out.write(json.dumps(doc) + "\n")
            
            frame_number += 1

    print(f"Successfully converted '{csv_filepath}' to '{json_filepath}'")
    print(f"Generated 1 metadata document and {frame_number} frame documents for Elasticsearch Bulk API.")
    print(f"---")
    print(f"You can now ingest this file into Elasticsearch using curl:")
    print(f"curl -s -H \"Content-Type: application/x-ndjson\" -XPOST \"http://localhost:9200/_bulk\" --data-binary @{os.path.basename(json_filepath)}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python convert_csv_to_es_bulk.py <path_to_csv> [index_name]")
        sys.exit(1)
        
    csv_path = sys.argv[1]
    index_name = sys.argv[2] if len(sys.argv) > 2 else "unreal-profiling"
    
    if not os.path.exists(csv_path):
        print(f"Error: File '{csv_path}' not found.")
        sys.exit(1)
        
    convert(csv_path, index_name)
