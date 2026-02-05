"""Convert text log files to colored HTML with search filtering."""

import argparse
import re
from html import escape
from pathlib import Path

# Define log level color patterns
# Order matters! First match wins.
LOG_PATTERNS = {
    "ERROR": (r"\b(?:Error|ERROR)\b", "#FF0000"),  # Red
    "WARNING": (r"\b(?:Warning|WARNING)\b", "#FFA500"),  # Orange
    "CMD": (r"\bCmd:", "#00FF00"),  # Green
    "SUCCESS": (r"\b(?:Success|SUCCESS|completed successfully)\b", "#00FF00"),  # Green
    "CONFIG": (r"(?:LogConfig|cvar|\.ini)", "#6495ED"),  # Cornflower Blue
    "LOGTEMP": (r"\bLogTemp\b", "#FF00FF"),  # Magenta
    "INFO": (r"\b(?:Info|INFO)\b", "#000000"),  # Black (default)
}

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        :root {{
            --bg-color: #1e1e2e;
            --container-bg: rgba(255, 255, 255, 0.05);
            --text-color: #e0e0e0;
            --text-muted: #a0a0b0;
            --accent-color: #7dd3fc;
            --border-color: rgba(125, 211, 252, 0.2);
            --header-bg: rgba(255, 255, 255, 0.08);
            --log-bg: rgba(0, 0, 0, 0.4);
            --transition-speed: 0.3s;
        }}

        body.light-mode {{
            --bg-color: #f8fafc;
            --container-bg: #ffffff;
            --text-color: #0f172a;
            --text-muted: #475569;
            --accent-color: #2563eb;
            --border-color: #cbd5e1;
            --header-bg: #f1f5f9;
            --log-bg: #ffffff;
        }}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            background: var(--bg-color);
            color: var(--text-color);
            padding: 20px;
            min-height: 100vh;
            transition: background-color var(--transition-speed), color var(--transition-speed);
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: var(--container-bg);
            backdrop-filter: blur(10px);
            border-radius: 12px;
            padding: 30px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
            position: relative;
        }}
        
        h1 {{
            color: var(--accent-color);
            margin-bottom: 25px;
            font-size: 28px;
            font-weight: 600;
            text-align: center;
        }}
        
        .controls-container {{
            background: var(--header-bg);
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 25px;
            border: 1px solid var(--border-color);
        }}

        .search-container {{
            display: flex;
            gap: 15px;
            align-items: center;
            margin-bottom: 15px;
        }}
        
        .search-label {{
            color: var(--text-muted);
            font-size: 14px;
            font-weight: 500;
            min-width: 80px;
        }}
        
        #searchInput {{
            flex: 1;
            padding: 12px 16px;
            border: 2px solid var(--border-color);
            border-radius: 6px;
            background: rgba(var(--bg-color), 0.1);
            color: var(--text-color);
            font-size: 14px;
            font-family: inherit;
            transition: all 0.3s ease;
        }}
        
        #searchInput:focus {{
            outline: none;
            border-color: var(--accent-color);
            box-shadow: 0 0 20px rgba(125, 211, 252, 0.2);
        }}
        
        .filter-buttons {{
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            margin-left: 95px; /* Align with input */
        }}
        
        .filter-btn {{
            padding: 8px 16px;
            border: 1px solid var(--border-color);
            border-radius: 20px;
            background: var(--header-bg);
            color: var(--text-muted);
            cursor: pointer;
            font-size: 13px;
            transition: all 0.2s ease;
        }}
        
        .filter-btn:hover {{
            background: var(--accent-color);
            color: white;
            transform: translateY(-1px);
        }}
        
        .filter-btn.active {{
            background: var(--accent-color);
            border-color: var(--accent-color);
            color: #fff;
            box-shadow: 0 0 10px rgba(125, 211, 252, 0.2);
        }}
        
        /* Button specific colors when active */
        .filter-btn[data-filter="error"].active {{ background: rgba(255, 0, 0, 0.2); border-color: #FF0000; }}
        .filter-btn[data-filter="warning"].active {{ background: rgba(255, 165, 0, 0.2); border-color: #FFA500; }}
        .filter-btn[data-filter="success"].active {{ background: rgba(0, 255, 0, 0.2); border-color: #00FF00; }}
        .filter-btn[data-filter="config"].active {{ background: rgba(100, 149, 237, 0.2); border-color: #6495ED; }}
        .filter-btn[data-filter="logtemp"].active {{ background: rgba(255, 0, 255, 0.2); border-color: #FF00FF; }}

        .clear-btn {{
            padding: 12px 24px;
            background: linear-gradient(135deg, #f43f5e 0%, #dc2626 100%);
            color: white;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 500;
            transition: all 0.3s ease;
        }}
        
        .stats {{
            display: flex;
            justify-content: space-between;
            margin-bottom: 15px;
            padding: 12px;
            background: var(--header-bg);
            border-radius: 6px;
            font-size: 13px;
            color: var(--text-muted);
            border: 1px solid var(--border-color);
        }}
        
        .log-container {{
            background: var(--log-bg);
            border-radius: 8px;
            padding: 20px;
            max-height: 800px;
            overflow-y: auto;
            border: 1px solid var(--border-color);
        }}
        
        .log-container::-webkit-scrollbar {{
            width: 10px;
        }}
        
        .log-container::-webkit-scrollbar-track {{
            background: rgba(255, 255, 255, 0.05);
            border-radius: 5px;
        }}
        
        .log-container::-webkit-scrollbar-thumb {{
            background: linear-gradient(180deg, #7dd3fc 0%, #3b82f6 100%);
            border-radius: 5px;
        }}
        
        .log-line {{
            padding: 8px 12px;
            margin: 4px 0;
            border-left: 3px solid transparent;
            border-radius: 4px;
            line-height: 1.6;
            font-size: 13px;
            word-wrap: break-word;
            transition: all 0.2s ease;
            cursor: text;
            user-select: text;
        }}
        
        .log-line:hover {{
            background: rgba(255, 255, 255, 0.08);
            transform: translateX(2px);
        }}
        
        .log-line.hidden {{
            display: none;
        }}
        
        .log-line.highlight {{
            background: rgba(251, 191, 36, 0.2);
            border-left-color: #fbbf24;
        }}
        
        /* Log level specific colors */
        .log-error {{ color: #e11d48; border-left-color: #e11d48; font-weight: 500; }}
        .log-warning {{ color: #d97706; border-left-color: #f59e0b; font-weight: 500; }}
        .log-cmd, .log-success {{ color: #16a34a; border-left-color: #22c55e; }}
        .log-config {{ color: #2563eb; border-left-color: #3b82f6; }}
        .log-logtemp {{ color: #9333ea; border-left-color: #a855f7; }}
        .log-info {{ color: var(--text-color); border-left-color: var(--border-color); }}

        body.light-mode .log-error {{ color: #9f1239; background: #fff1f2; }}
        body.light-mode .log-warning {{ color: #92400e; background: #fffbeb; }}
        body.light-mode .log-cmd, body.light-mode .log-success {{ color: #15803d; background: #f0fdf4; }}
        body.light-mode .log-config {{ color: #1e40af; background: #eff6ff; }}
        body.light-mode .log-logtemp {{ color: #6b21a8; background: #faf5ff; }}
        
        .no-results {{
            text-align: center;
            padding: 40px;
            color: var(--text-muted);
            font-size: 16px;
        }}

        .theme-toggle {{
            position: absolute;
            top: 25px;
            right: 30px;
            background: var(--header-bg);
            border: 1px solid var(--border-color);
            color: var(--text-color);
            width: 40px;
            height: 40px;
            border-radius: 50%;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            transition: all 0.3s ease;
            z-index: 1000;
        }}

        .theme-toggle:hover {{
            transform: scale(1.1);
            border-color: var(--accent-color);
        }}
        
        mark {{
            background-color: rgba(251, 191, 36, 0.4);
            color: inherit;
            padding: 2px 4px;
            border-radius: 2px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <button class="theme-toggle" id="theme-toggle" title="Toggle Light/Dark Mode">
            <span id="theme-icon">🌙</span>
        </button>
        <h1>{title}</h1>
        
        <div class="controls-container">
            <div class="search-container">
                <label class="search-label" for="searchInput">Filter Logs:</label>
                <input 
                    type="text" 
                    id="searchInput" 
                    placeholder="Type to search logs..."
                    autocomplete="off"
                >
                <button class="clear-btn" onclick="clearSearch()">Clear</button>
            </div>
            
            <div class="filter-buttons">
                <button class="filter-btn active" data-filter="all" onclick="setFilter('all')">All</button>
                <button class="filter-btn" data-filter="error" onclick="setFilter('error')">Errors</button>
                <button class="filter-btn" data-filter="warning" onclick="setFilter('warning')">Warnings</button>
                <button class="filter-btn" data-filter="logtemp" onclick="setFilter('logtemp')">LogTemp</button>
                <button class="filter-btn" data-filter="config" onclick="setFilter('config')">Config</button>
                <button class="filter-btn" data-filter="success" onclick="setFilter('success')">Success</button>
            </div>
        </div>
        
        <div class="stats">
            <span>Total Lines: <strong id="totalLines">{total_lines}</strong></span>
            <span>Visible Lines: <strong id="visibleLines">{total_lines}</strong></span>
        </div>
        
        <div class="log-container" id="logContainer">
{log_lines}
        </div>
    </div>
    
    <script>
        // Theme Toggle Logic
        const themeToggle = document.getElementById('theme-toggle');
        const themeIcon = document.getElementById('theme-icon');
        const body = document.body;

        function updateThemeIcon() {{
            if (body.classList.contains('light-mode')) {{
                themeIcon.innerText = '☀️';
            }} else {{
                themeIcon.innerText = '🌙';
            }}
        }}

        // Auto-detect theme (Preference > OS > Default Dark)
        const savedTheme = localStorage.getItem('theme');
        const osPrefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        
        if (savedTheme === 'light' || (!savedTheme && !osPrefersDark)) {{
            body.classList.add('light-mode');
            updateThemeIcon();
        }}

        themeToggle.addEventListener('click', () => {{
            body.classList.toggle('light-mode');
            const isLight = body.classList.contains('light-mode');
            localStorage.setItem('theme', isLight ? 'light' : 'dark');
            updateThemeIcon();
        }});

        // Move to Top Button
        const scrollBtn = document.createElement("button");
        scrollBtn.innerHTML = "↑";
        scrollBtn.id = "scrollTopBtn";
        scrollBtn.style.cssText = `
            position: fixed;
            bottom: 30px;
            right: 30px;
            display: none;
            background-color: var(--accent-color);
            color: white;
            border: none;
            border-radius: 50%;
            width: 50px;
            height: 50px;
            font-size: 24px;
            cursor: pointer;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            z-index: 1000;
            transition: opacity 0.3s, transform 0.2s;
        `;
        scrollBtn.onmouseover = () => scrollBtn.style.transform = "scale(1.1)";
        scrollBtn.onmouseout = () => scrollBtn.style.transform = "scale(1)";
        scrollBtn.onclick = () => window.scrollTo({{top: 0, behavior: 'smooth'}});
        document.body.appendChild(scrollBtn);

        window.onscroll = () => {{
            if (document.body.scrollTop > 200 || document.documentElement.scrollTop > 200) {{
                scrollBtn.style.display = "block";
            }} else {{
                scrollBtn.style.display = "none";
            }}
        }};

        const searchInput = document.getElementById('searchInput');
        const logLines = document.querySelectorAll('.log-line');
        const visibleLinesSpan = document.getElementById('visibleLines');
        const filterBtns = document.querySelectorAll('.filter-btn');
        
        let currentFilter = 'all';
        let searchTimeout;
        
        searchInput.addEventListener('input', function(e) {{
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {{
                applyFilters();
            }}, 150);
        }});
        
        function setFilter(filterType) {{
            currentFilter = filterType;
            
            // Update button states
            filterBtns.forEach(btn => {{
                if (btn.getAttribute('data-filter') === filterType) {{
                    btn.classList.add('active');
                }} else {{
                    btn.classList.remove('active');
                }}
            }});
            
            applyFilters();
        }}
        
        function applyFilters() {{
            const searchTerm = searchInput.value.toLowerCase().trim();
            let visibleCount = 0;
            
            logLines.forEach(line => {{
                const text = line.textContent.toLowerCase();
                const isTypeMatch = currentFilter === 'all' || line.classList.contains('log-' + currentFilter);
                const isSearchMatch = !searchTerm || text.includes(searchTerm);
                
                if (isTypeMatch && isSearchMatch) {{
                    line.classList.remove('hidden');
                    visibleCount++;
                    
                    // Highlight matching text
                    if (searchTerm) {{
                        const originalText = line.getAttribute('data-original') || line.textContent;
                        line.setAttribute('data-original', originalText);
                        
                        const regex = new RegExp(`(${{escapeRegex(searchInput.value)}})`, 'gi');
                        line.innerHTML = originalText.replace(regex, '<mark>$1</mark>');
                        line.classList.add('highlight');
                    }} else {{
                        const originalText = line.getAttribute('data-original');
                        if (originalText) {{
                            line.textContent = originalText;
                        }}
                        line.classList.remove('highlight');
                    }}
                }} else {{
                    line.classList.add('hidden');
                }}
            }});
            
            visibleLinesSpan.textContent = visibleCount;
            
            // Show no results message
            const logContainer = document.getElementById('logContainer');
            let noResultsMsg = document.getElementById('noResults');
            
            if (visibleCount === 0) {{
                if (!noResultsMsg) {{
                    noResultsMsg = document.createElement('div');
                    noResultsMsg.id = 'noResults';
                    noResultsMsg.className = 'no-results';
                    noResultsMsg.textContent = 'No matching logs found';
                    logContainer.appendChild(noResultsMsg);
                }}
            }} else if (noResultsMsg) {{
                noResultsMsg.remove();
            }}
        }}
        
        function clearSearch() {{
            searchInput.value = '';
            applyFilters();
        }}
        
        function escapeRegex(string) {{
            return string.replace(/[.*+?^${{}}()|[\\]\\\\]/g, '\\\\$&');
        }}
        
        // Allow copying log lines
        logLines.forEach(line => {{
            line.addEventListener('dblclick', function() {{
                const text = this.getAttribute('data-original') || this.textContent;
                navigator.clipboard.writeText(text).then(() => {{
                    // Visual feedback
                    const originalBg = this.style.background;
                    this.style.background = 'rgba(125, 211, 252, 0.3)';
                    setTimeout(() => {{
                        this.style.background = originalBg;
                    }}, 300);
                }});
            }});
        }});
    </script>
</body>
</html>
"""


def detect_log_level(line: str) -> str:
    """Detect the log level of a line based on patterns."""
    # Check in priority order
    for level, (pattern, _) in LOG_PATTERNS.items():
        if re.search(pattern, line):
            return level.lower()
    return "info"


def convert_log_to_html(input_file: Path, output_file: Path) -> None:
    """Convert a text log file to HTML with colored formatting."""
    try:
        # Read the log file
        with open(input_file, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        # Generate HTML for each log line
        log_html_lines = []
        for i, line in enumerate(lines, 1):
            line = line.rstrip("\n\r")
            if not line.strip():
                continue

            # Escape HTML characters
            escaped_line = escape(line)

            # Detect log level
            log_level = detect_log_level(line)

            # Create HTML log line
            log_html = f'            <div class="log-line log-{log_level}">{escaped_line}</div>'
            log_html_lines.append(log_html)

        # Generate the complete HTML
        html_content = HTML_TEMPLATE.format(
            title=f"Log Viewer - {input_file.name}",
            total_lines=len(log_html_lines),
            log_lines="\n".join(log_html_lines),
        )

        # Write the HTML file
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html_content)

        print(f"✓ Successfully converted {input_file.name} to {output_file.name}")
        print(f"  - Total lines: {len(log_html_lines)}")

    except Exception as e:
        print(f"✗ Error converting {input_file.name}: {e}")
        raise


def main():
    """Main entry point for the log converter."""
    parser = argparse.ArgumentParser(
        description="Convert text log files to colored HTML with search filtering"
    )
    parser.add_argument(
        "-i", "--input", type=str, required=True, help="Input log file path"
    )
    parser.add_argument(
        "-o", "--output", type=str, required=True, help="Output HTML file path"
    )

    args = parser.parse_args()

    input_file = Path(args.input)
    output_file = Path(args.output)

    if not input_file.exists():
        print(f"✗ Error: Input file not found: {input_file}")
        return 1

    # Ensure output directory exists
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Convert the log file
    convert_log_to_html(input_file, output_file)

    return 0


if __name__ == "__main__":
    exit(main())
