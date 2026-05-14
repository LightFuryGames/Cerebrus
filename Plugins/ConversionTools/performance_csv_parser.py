import csv
import json
import os
import re
import argparse
from typing import Dict, Any, List
import numpy as np

class PerformanceCSVParser:
    def __init__(self, csv_path: str):
        self.csv_path = csv_path
        self.device_id = os.path.basename(os.path.dirname(csv_path))
        
        # Read file lines to extract metadata from the end
        with open(csv_path, 'r', encoding='utf-8-sig', errors='ignore') as f:
            self.lines = f.readlines()
            
        self.metadata = self._extract_metadata()
        self.data = self._load_csv_data()

    def _extract_metadata(self) -> Dict[str, str]:
        metadata = {}
        if not self.lines:
            return metadata
            
        # Check the last line for metadata
        last_line = self.lines[-1].strip()
        if "[HasHeaderRowAtEnd]" in last_line:
            try:
                row = next(csv.reader([last_line]))
                # Format is [key],value,[key2],value2...
                for i in range(0, len(row), 2):
                    if i + 1 < len(row):
                        key = row[i].strip('[]')
                        # Map to user-friendly keys if possible
                        friendly_key = {
                            "buildversion": "Build Version",
                            "platform": "platform",
                            "deviceprofile": "DeviceProfile",
                            "os": "OS",
                            "cpu": "CPU/Device",
                            "captureduration": "Capture Duration",
                            "commandline": "Command Line",
                            "targetframerate": "Target Framerate"
                        }.get(key, key)
                        metadata[friendly_key] = row[i+1]
            except Exception:
                pass
        return metadata

    def _load_csv_data(self) -> Dict[str, List[float]]:
        data = {}
        # Find where the data rows start (usually after the first header line)
        # We need to skip the metadata line at the end
        csv_lines = self.lines
        if csv_lines and "[HasHeaderRowAtEnd]" in csv_lines[-1]:
            csv_lines = csv_lines[:-1]
            
        # DictReader uses the first line as header
        reader = csv.DictReader(csv_lines)
        for row in reader:
            for key, val in row.items():
                if key and val:
                    try:
                        if key not in data:
                            data[key] = []
                        data[key].append(float(val))
                    except ValueError:
                        pass
        return data

    def parse(self) -> Dict[str, Any]:
        # Start with device_id and metadata
        flat_data = {
            "device_id": self.device_id
        }
        
        # Extract timestamp from filename like Profile(20260427_050858).csv
        match = re.search(r'\((\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})\)', os.path.basename(self.csv_path))
        if match:
            year, month, day, hour, minute, second = match.groups()
            flat_data["Profiling Timestamp"] = f"{day}:{month}:{year}:{hour}:{minute}:{second}"
            
        flat_data.update(self.metadata)

        
        # Calculate summary metrics for FPS Chart
        # Target Framerate (default to 60 if not found)
        target_fps = 60.0
        if "Target Framerate" in self.metadata:
            try:
                target_fps = float(self.metadata["Target Framerate"])
            except ValueError:
                pass
        
        target_ms = 1000.0 / target_fps
        
        # FrameTime stats
        if "FrameTime" in self.data:
            frame_times = np.array(self.data["FrameTime"])
            total_frames = len(frame_times)
            duration_s = np.sum(frame_times) / 1000.0
            
            flat_data["Frame count"] = f"{total_frames} (0 excluded)"
            flat_data["Total Time (s)"] = round(duration_s, 2)
            
            avg_ft = np.mean(frame_times)
            flat_data["Frametime Avg"] = round(float(avg_ft), 2)
            flat_data["FPS Avg"] = round(1000.0 / avg_ft, 2)
            
            # Hitches
            hitches_60 = np.sum(frame_times > 60.0)
            flat_data["Hitches/Min"] = round(float(hitches_60 / (duration_s / 60.0)), 2)
            
            hitch_time = np.sum(frame_times[frame_times > 60.0])
            flat_data["HitchTimePercent"] = round(float((hitch_time / (duration_s * 1000.0)) * 100.0), 2)
            
            # MVP60 approximation (percentage of frames hitting target)
            frames_hitting_target = np.sum(frame_times <= target_ms)
            flat_data[f"MVP{int(target_fps)}"] = round(float((frames_hitting_target / total_frames) * 100.0), 2)
            
            # Statistics
            flat_data["Standard Deviation (SD)"] = round(float(np.std(1000.0 / frame_times)), 2) # SD of FPS
            flat_data["Interquartile Range (IQR)"] = round(float(np.percentile(1000.0 / frame_times, 75) - np.percentile(1000.0 / frame_times, 25)), 2)
            
            # Percentiles of FPS
            fps_vals = 1000.0 / frame_times
            for p in [1, 5, 50, 90, 95, 99]:
                flat_data[f"{p}th Percentile"] = round(float(np.percentile(fps_vals, p)), 1)

            # Thread stats
            for thread in ["GameThreadTime", "RenderThreadTime", "RHIThreadTime", "GPUTime"]:
                if thread in self.data:
                    flat_data[f"{thread} Avg"] = round(float(np.mean(self.data[thread])), 2)

            # Hitches Table
            thresholds = [60, 150, 250, 500, 750, 1000, 2000]
            for row_name in ["FrameTime", "GameThreadTime", "RenderThreadTime", "RHIThreadTime", "GPUTime"]:
                if row_name in self.data:
                    row_vals = np.array(self.data[row_name])
                    for t in thresholds:
                        flat_data[f"{row_name}_>{t}ms"] = int(np.sum(row_vals > t))

        # Memory and other metrics
        if "MemoryFreeMB" in self.data:
            flat_data["MemoryFreeMB Min"] = round(float(np.min(self.data["MemoryFreeMB"])), 2)
        if "PhysicalUsedMB" in self.data:
            flat_data["PhysicalUsedMB Max"] = round(float(np.max(self.data["PhysicalUsedMB"])), 2)
        if "RHI/DrawCalls" in self.data:
            flat_data["RHI/Drawcalls Avg"] = round(float(np.mean(self.data["RHI/DrawCalls"])), 2)
        elif "RHI/Drawcalls" in self.data:
             flat_data["RHI/Drawcalls Avg"] = round(float(np.mean(self.data["RHI/Drawcalls"])), 2)

        return flat_data

def main():
    parser = argparse.ArgumentParser(description="Parse Unreal Engine CSV performance reports to flat JSON.")
    parser.add_argument("input", help="Path to the CSV report file.")
    parser.add_argument("-o", "--output", help="Path to save the JSON output. Defaults to <input>.json")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input):
        print(f"Error: File not found: {args.input}")
        return

    report_parser = PerformanceCSVParser(args.input)
    data = report_parser.parse()
    
    output_path = args.output or f"{os.path.splitext(args.input)[0]}.json"
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
        
    print(f"Successfully parsed CSV report to {output_path}")

if __name__ == "__main__":
    main()
