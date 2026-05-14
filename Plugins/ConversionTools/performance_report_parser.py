import json
import re
import os
import argparse
from typing import Dict, Any, List

class PerformanceReportParser:
    def __init__(self, html_path: str):
        self.html_path = html_path
        with open(html_path, 'r', encoding='utf-8') as f:
            self.content = f.read()

    def parse(self) -> Dict[str, Any]:
        flat_data = {
            "device_id": os.path.basename(os.path.dirname(self.html_path))
        }
        
        # Merge metadata
        metadata = self._extract_metadata()
        flat_data.update(metadata)
        
        # Merge FPS chart
        fps_chart = self._extract_fps_chart()
        flat_data.update(fps_chart)
        
        # Merge hitches (prefix with row_name)
        hitches = self._extract_hitches()
        for row_name, cols in hitches.items():
            for col_name, value in cols.items():
                flat_data[f"{row_name}_{col_name}"] = value
                
        # Merge statistics
        stats = self._extract_statistics()
        if "Percentiles" in stats:
            for p_name, p_val in stats["Percentiles"].items():
                flat_data[f"{p_name} Percentile"] = p_val
            del stats["Percentiles"]
        flat_data.update(stats)
            
        return flat_data

    def _extract_metadata(self) -> Dict[str, str]:
        metadata = {}
        # Find the metadata table
        # Structure: <tr><td bgcolor='#F0F0F0'>Key</td><td><b>Value</b></td></tr> or <td>Value</td>
        pattern = r"<tr><td bgcolor='#F0F0F0'>(.*?)</td><td>(?:<b>)?(.*?)(?:</b>)?</td></tr>"
        matches = re.findall(pattern, self.content)
        for key, value in matches:
            # Clean up value (sometimes it has HTML entities like &#44; for comma)
            value = value.replace('&#44;', ',')
            metadata[key.strip()] = value.strip()
        
        # Also catch Configuration, OS, CPU/Device etc which might not have bgcolor
        extra_pattern = r"<tr><td>(Configuration|OS|CPU/Device|Capture Duration|Command Line|Features|Target Framerate)</td><td>(?:<b>)?(.*?)(?:</b>)?</td></tr>"
        extra_matches = re.findall(extra_pattern, self.content)
        for key, value in extra_matches:
            value = value.replace('&#44;', ',')
            metadata[key.strip()] = value.strip()
            
        return metadata

    def _extract_fps_chart(self) -> Dict[str, Any]:
        fps_data = {}
        # Find the FPSChart table headers
        header_row_pattern = r"<tr>\s*<th>Section Name</th>(.*?)</tr>"
        header_row_match = re.search(header_row_pattern, self.content, re.DOTALL)
        if not header_row_match:
            return {}
            
        # Extract all headers including those with styles
        headers = ["Section Name"]
        header_cells = re.findall(r"<th.*?>(.*?)</th>", header_row_match.group(1), re.DOTALL)
        headers.extend([h.replace('<wbr>', '').strip() for h in header_cells])

        # Find "Entire Run" row
        row_pattern = r"<tr>\s*<td>Entire Run</td>(.*?)</tr>"
        row_match = re.search(row_pattern, self.content, re.DOTALL)
        if row_match:
            values = re.findall(r"<td.*?>(.*?)</td>", row_match.group(1), re.DOTALL)
            # Remove any nested tags like <b> or <span>
            clean_values = []
            for v in values:
                cv = re.sub(r"<.*?>", "", v).strip()
                clean_values.append(cv)
                
            # Map headers to values
            for i, val in enumerate(clean_values):
                if i + 1 < len(headers):
                    key = headers[i+1]
                    try:
                        # Handle potential empty or non-numeric values
                        if val:
                            fps_data[key] = float(val)
                        else:
                            fps_data[key] = None
                    except ValueError:
                        fps_data[key] = val
        
        return fps_data

    def _extract_hitches(self) -> Dict[str, Dict[str, int]]:
        hitches = {}
        # Find the Hitches table headers to get thresholds
        # The header row starts with <td></td> and then several <th> cells
        hitch_header_row_pattern = r"<tr>\s*<td></td>\s*(.*?)</tr>"
        hitch_header_match = re.search(hitch_header_row_pattern, self.content, re.DOTALL)
        
        cols = []
        if hitch_header_match:
            # Extract thresholds from <th> cells
            # They look like <th> >60ms</b></td> or similar
            th_cells = re.findall(r"<th.*?>(.*?)</th>", hitch_header_match.group(1), re.DOTALL)
            for th in th_cells:
                # Clean and extract the threshold (e.g., ">60ms")
                clean_th = re.sub(r"<.*?>", "", th).strip()
                if clean_th:
                    cols.append(clean_th)
        
        if not cols:
            # Fallback to defaults if parsing fails
            cols = [">60ms", ">150ms", ">250ms", ">500ms", ">750ms", ">1000ms", ">2000ms"]
        
        rows = ["FrameTime", "GameThreadTime", "RenderThreadTime", "RHIThreadTime", "GPUTime"]
        for row_name in rows:
            # Match row name with possible tags/whitespace
            pattern = rf"<tr>\s*<td>\s*<b>{row_name}</b>\s*</td>(.*?)</tr>"
            match = re.search(pattern, self.content, re.DOTALL)
            if match:
                values = re.findall(r"<td.*?>(.*?)</td>", match.group(1), re.DOTALL)
                row_data = {}
                for i, val in enumerate(values):
                    if i < len(cols):
                        clean_val = re.sub(r"<.*?>", "", val).strip()
                        try:
                            row_data[cols[i]] = int(clean_val)
                        except ValueError:
                            row_data[cols[i]] = clean_val
                hitches[row_name] = row_data
        
        return hitches



    def _extract_statistics(self) -> Dict[str, Any]:
        stats = {
            "Percentiles": {}
        }
        
        # 1. Extract SD and IQR from the breakdown text
        sd_match = re.search(r"Standard Deviation \(SD\): ([\d.]+) FPS", self.content)
        if sd_match:
            stats["Standard Deviation (SD)"] = float(sd_match.group(1))
            
        iqr_match = re.search(r"Interquartile Range \(IQR\): ([\d.]+) FPS", self.content)
        if iqr_match:
            stats["Interquartile Range (IQR)"] = float(iqr_match.group(1))
            
        # 2. Extract Percentiles from Gauge labels and values
        # Gauge structure: 
        # <div class="gauge-title" ...>99th Percentile, Target is 60</div>
        # ...
        # <text ...>86.8</text>
        gauge_pattern = r"<div class=\"gauge-title\".*?>(.*?) Percentile.*?</div>.*?<text x=\"100\" y=\"85\".*?>(.*?)</text>"
        gauge_matches = re.findall(gauge_pattern, self.content, re.DOTALL)
        for p_name, p_val in gauge_matches:
            stats["Percentiles"][p_name.strip()] = float(p_val.strip())
            
        return stats

def main():
    parser = argparse.ArgumentParser(description="Parse Unreal Engine HTML performance reports to JSON.")
    parser.add_argument("input", help="Path to the HTML report file.")
    parser.add_argument("-o", "--output", help="Path to save the JSON output. Defaults to <input>.json")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input):
        print(f"Error: File not found: {args.input}")
        return

    report_parser = PerformanceReportParser(args.input)
    data = report_parser.parse()
    
    output_path = args.output or f"{os.path.splitext(args.input)[0]}.json"
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
        
    print(f"Successfully parsed report to {output_path}")

if __name__ == "__main__":
    main()
