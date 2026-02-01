
"""
HTML Template for MemReport
"""

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        :root {{
            --bg-color: #1e1e1e;
            --text-color: #e0e0e0;
            --accent-color: #3b82f6;
            --border-color: #333;
            --header-bg: #2d2d2d;
            --row-even: #252525;
            --row-odd: #1e1e1e;
            --hover-bg: #3a3a3a;
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            line-height: 1.6;
            padding: 20px;
        }}

        .container {{
            max-width: 1600px;
            margin: 0 auto;
        }}

        h1 {{
            margin-bottom: 20px;
            color: var(--accent-color);
        }}

        /* Tabs */
        .tabs {{
            display: flex;
            border-bottom: 1px solid var(--border-color);
            margin-bottom: 20px;
            flex-wrap: wrap;
        }}

        .tab-btn {{
            padding: 10px 20px;
            background: none;
            border: none;
            color: var(--text-color);
            cursor: pointer;
            font-size: 14px;
            transition: all 0.3s ease;
            opacity: 0.7;
            border-bottom: 2px solid transparent;
        }}

        .tab-btn:hover {{
            opacity: 1;
            background-color: rgba(255, 255, 255, 0.05);
        }}

        .tab-btn.active {{
            opacity: 1;
            border-bottom-color: var(--accent-color);
            background-color: rgba(59, 130, 246, 0.1);
        }}

        /* Content */
        .tab-content {{
            display: none;
            padding: 20px;
            background-color: var(--row-odd);
            border-radius: 8px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
        }}

        .tab-content.active {{
            display: block;
            animation: fadeIn 0.3s ease;
        }}

        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(10px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}

        /* Stats Grid */
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 15px;
        }}

        .stat-card {{
            background-color: var(--header-bg);
            padding: 15px;
            border-radius: 6px;
            border: 1px solid var(--border-color);
        }}

        .stat-label {{
            font-size: 12px;
            color: #888;
            margin-bottom: 5px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        .stat-value {{
            font-size: 18px;
            font-weight: 600;
            word-wrap: break-word;
            overflow-wrap: break-word;
            word-break: break-all;
        }}

        /* Tables */
        .table-container {{
            overflow-x: auto;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }}

        th, td {{
            padding: 10px;
            text-align: left;
            border-bottom: 1px solid var(--border-color);
            word-wrap: break-word;
            white-space: normal;
            max-width: 400px; /* Prevent single columns from dominating */
        }}
        
        /* Tree View */
        .tree-node {{
            margin-bottom: 5px;
            border: 1px solid var(--border-color);
            border-radius: 4px;
            background-color: var(--header-bg);
        }}
        
        .tree-summary {{
            padding: 10px;
            cursor: pointer;
            font-weight: 600;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        
        .tree-summary:hover {{
            background-color: var(--hover-bg);
        }}
        
        .tree-content {{
            padding: 10px;
            background-color: var(--row-odd);
            border-top: 1px solid var(--border-color);
        }}
        
        .tree-child {{
            padding: 5px 10px;
            margin: 2px 0;
            border-bottom: 1px solid rgba(255,255,255,0.05);
            font-family: monospace;
            font-size: 12px;
        }}

        th {{
            background-color: var(--header-bg);
            font-weight: 600;
            position: sticky;
            top: 0;
            cursor: pointer;
            user-select: none;
        }}

        th:hover {{
            background-color: #383838;
        }}

        tr:nth-child(even) {{
            background-color: var(--row-even);
        }}

        tr:hover {{
            background-color: var(--hover-bg);
        }}

        .numeric {{
            text-align: right;
            font-family: 'Consolas', monospace;
        }}
        
        .search-container {{
            margin-bottom: 15px;
        }}
        
        input[type="text"] {{
            width: 100%;
            padding: 10px;
            background-color: var(--row-even);
            border: 1px solid var(--border-color);
            color: var(--text-color);
            border-radius: 4px;
        }}
        
        input[type="text"]:focus {{
            outline: none;
            border-color: var(--accent-color);
        }}
        
        /* Loading */
        .loading {{
            color: #888;
            font-style: italic;
            padding: 20px;
            text-align: center;
        }}

    </style>
</head>
<body>
    <div class="container">
        <h1>{report_title}</h1>

        <div class="tabs" id="tabs">
            {tab_buttons}
        </div>

        {tab_contents}
    </div>

    <script>
        function openTab(evt, tabName) {{
            var i, tabContent, tabBtns;
            
            tabContent = document.getElementsByClassName("tab-content");
            for (i = 0; i < tabContent.length; i++) {{
                tabContent[i].style.display = "none";
                tabContent[i].classList.remove("active");
            }}

            tabBtns = document.getElementsByClassName("tab-btn");
            for (i = 0; i < tabBtns.length; i++) {{
                tabBtns[i].className = tabBtns[i].className.replace(" active", "");
            }}

            document.getElementById(tabName).style.display = "block";
            
            // Trigger reflow to enable animation
            void document.getElementById(tabName).offsetWidth;
            document.getElementById(tabName).classList.add("active");
            
            evt.currentTarget.className += " active";
        }}
        
        function filterTree(containerId, term) {{
            const container = document.getElementById(containerId);
            const nodes = container.querySelectorAll('.tree-node, .tree-child');
            term = term.toLowerCase();
            
            if (!term) {{
                // Show everything
                nodes.forEach(n => n.style.display = "");
                return;
            }}
            
            // Expand all details when searching
            const details = container.querySelectorAll('details');
            details.forEach(d => d.open = true);
            
            // This is a naive filter for tree structures, improving it requires more logic.
            // For now, let's keep it simple: Show block if text matches.
        }}
        
        function filterTable(tableId, colIndex, term) {{
            const table = document.getElementById(tableId);
            const rows = table.getElementsByTagName('tr');
            term = term.toLowerCase();
            
            // Start from 1 to skip header
            for(let i=1; i < rows.length; i++) {{
                const cell = rows[i].getElementsByTagName('td')[colIndex];
                if(cell) {{
                    const text = cell.innerText.toLowerCase();
                    rows[i].style.display = text.includes(term) ? "" : "none";
                }}
            }}
        }}

        // Simple Sortable Table Script
        document.querySelectorAll('th').forEach(th => {{
            th.addEventListener('click', () => {{
                const table = th.closest('table');
                const tbody = table.querySelector('tbody');
                const rows = Array.from(tbody.querySelectorAll('tr'));
                const index = Array.from(th.parentNode.children).indexOf(th);
                const isNumeric = th.classList.contains('numeric');
                const asc = th.getAttribute('data-asc') !== 'true'; // Toggle
                
                rows.sort((a, b) => {{
                    const aVal = a.children[index].innerText;
                    const bVal = b.children[index].innerText;
                    
                    if(isNumeric) {{
                        return (parseFloat(aVal.replace(/,/g, '')) - parseFloat(bVal.replace(/,/g, ''))) * (asc ? 1 : -1);
                    }} else {{
                        return aVal.localeCompare(bVal) * (asc ? 1 : -1);
                    }}
                }});
                
                rows.forEach(row => tbody.appendChild(row));
                th.setAttribute('data-asc', asc);
            }});
        }});
    </script>
</body>
</html>
"""
