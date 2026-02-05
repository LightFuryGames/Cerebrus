import re


def format_seconds_to_hms(seconds_str: str) -> str:
    """Converts seconds string (e.g. '8198.52') to verbose HH:MM:SS format."""
    try:
        # Remove 'Seconds' if present
        cleaned = re.sub(r"(?i)seconds", "", seconds_str).strip()
        total_seconds = float(cleaned)

        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        seconds = int(total_seconds % 60)

        return (
            f"{hours} hours : {minutes} minutes : {seconds} seconds ({cleaned} Seconds)"
        )
    except (ValueError, TypeError):
        return seconds_str


def format_memory_size(size_kb_val: float) -> str:
    """Formats raw KB value to MB if > 1MB (1024KB). Ensures separated units."""
    if size_kb_val > 1024:
        mb_val = size_kb_val / 1024.0
        return f"{mb_val:.2f} MB"
    return f"{size_kb_val:.2f} KB"


def format_bytes(bytes_val: float) -> str:
    """Formats raw bytes to KB/MB. 1 KB = 1024 Bytes, 1 MB = 1024 KB."""
    if bytes_val >= 1024 * 1024:
        return f"{bytes_val / (1024 * 1024):.2f} MB"
    if bytes_val >= 1024:
        return f"{bytes_val / 1024:.2f} KB"
    return f"{bytes_val:.2f} B"


def try_format_cell_value(header: str, value: str) -> str:
    """Attempts to format a cell value based on its header or content."""
    # Check if value is a numeric KB value
    val_clean = value.replace(",", "").strip()

    # Heuristic: Header contains "KB" or "MB" or "Size"
    if "KB" in header or "MB" in header or "Size" in header:
        try:
            # If value is just a number, assume KB if header says KB
            if "KB" in header:
                # Check if it already has units?
                match = re.search(r"([\d\.]+)", val_clean)
                if match:
                    flt_val = float(match.group(1))
                    return format_memory_size(flt_val)
        except:
            pass

    # Check if value string ends in KB/MB (common in summary tables)
    # Regex for "123.45 KB" or "123.45KB"
    # Improved: Allow optional space, force space in output
    # Updated Regex to be fully case insensitive and optional space
    match = re.search(r"^([\d\.,]+)\s*(KB|MB|GB)$", val_clean, re.IGNORECASE)
    if match:
        num_part = float(match.group(1).replace(",", ""))
        unit = match.group(2).upper()
        if unit == "KB":
            return format_memory_size(num_part)
        if unit == "MB":
            return f"{num_part:.2f} MB"

    # Fallback: Check if it LOOKS like it has units but no space (e.g. 710.95MB)
    # and just needs a space inserted.
    match_tight = re.search(r"^([\d\.,]+)(KB|MB|GB)$", val_clean, re.IGNORECASE)
    if match_tight:
        num_part = float(match_tight.group(1).replace(",", ""))
        unit = match_tight.group(2).upper()
        if unit == "KB":
            return format_memory_size(num_part)
        if unit == "MB":
            return f"{num_part:.2f} MB"

    return value
