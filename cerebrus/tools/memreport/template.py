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
            --text-muted: #888;
            --text-secondary: #aaa;
            --accent-color: #3b82f6;
            --border-color: #333;
            --header-bg: #2d2d2d;
            --row-even: #252525;
            --row-odd: #1e1e1e;
            --hover-bg: #3a3a3a;
            --transition-speed: 0.3s;
        }}

        body.light-mode {{
            --bg-color: #f8fafc;
            --text-color: #0f172a;
            --text-muted: #475569; /* Much darker slate for high contrast */
            --text-secondary: #1e293b;
            --accent-color: #2563eb;
            --border-color: #cbd5e1;
            --header-bg: #ffffff;
            --row-even: #f1f5f9;
            --row-odd: #ffffff;
            --hover-bg: #f8fafc;
        }}

        .unreal-red {{ 
            color: #f43f5e; 
            font-style: italic; 
            font-weight: 500; 
        }}
        body.light-mode .unreal-red {{ 
            color: #9f1239; 
        }}

        body {{
            transition: background-color var(--transition-speed), color var(--transition-speed);
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

        #device-info .stat-value {{
            font-size: 14px;
        }}

        /* Tables */
        .table-container {{
            width: 100%;
            overflow-x: auto;
            margin-bottom: 20px;
            border: 1px solid var(--border-color);
            border-radius: 4px;
            background-color: rgba(0,0,0,0.2);
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
            table-layout: auto; /* Allow auto layout to wrap */
        }}

        th, td {{
            padding: 12px 10px;
            text-align: left;
            border-bottom: 1px solid var(--border-color);
            border-right: 1px solid rgba(128,128,128,0.1); /* Subtle vertical lines */
            word-wrap: break-word;
            white-space: normal;
        }}

        /* Constrain Name column to prevent table explosion */
        /* Constrain columns to prevent table explosion, allow wrapping */
        th:nth-child(n+1), td:nth-child(n+1) {{
            max-width: 600px;
            min-width: 50px;
            word-break: break-all;
            white-space: normal;
        }}

        .theme-toggle {{
            position: absolute;
            top: 20px;
            right: 20px;
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

        /* Alerts & Feedback */
        .alert {{
            padding: 15px 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            border: 1px solid transparent;
            font-size: 14px;
            display: flex;
            align-items: flex-start;
            gap: 15px;
        }}
        .alert-icon {{
            font-size: 24px;
            flex-shrink: 0;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .alert-content {{
            flex-grow: 1;
        }}

        /* Dark Mode Alerts */
        .alert-info {{
            background: rgba(59, 130, 246, 0.1);
            border-color: rgba(59, 130, 246, 0.3);
            color: #60a5fa;
        }}
        .alert-warning {{
            background: rgba(245, 158, 11, 0.1);
            border-color: rgba(245, 158, 11, 0.3);
            color: #fbbf24;
        }}
        .alert-danger {{
            background: rgba(244, 63, 94, 0.1);
            border-color: rgba(244, 63, 94, 0.3);
            color: #fb7185;
        }}

        /* Light Mode Alerts */
        body.light-mode .alert-info {{
            background: #eff6ff;
            border-color: #bfdbfe;
            color: #1e40af;
            font-weight: 500;
        }}
        body.light-mode .alert-warning {{
            background: #fffbeb;
            border-color: #fcd34d;
            color: #92400e;
            font-weight: 500;
        }}
        body.light-mode .alert-danger {{
            background: #fff1f2;
            border-color: #fda4af;
            color: #9f1239;
            font-weight: 500;
        }}

        /* Keyword Highlights */
        .alert-content b, .alert-content strong {{
            font-weight: 700;
        }}
        .alert-danger .alert-content strong {{
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        th:last-child, td:last-child {{
            border-right: none;
        }}
        
        /* Tree View - PRESERVED CRITICAL STYLES */
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
            /* Ensure indentation for nested items */
            padding-left: 20px; 
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

        /* Sort Icons */
        th {{
            cursor: pointer;
            user-select: none;
            position: relative;
        }}
        th::after {{
            content: '';
            position: absolute;
            right: 5px;
            font-size: 10px;
        }}
        th.sort-asc::after {{
            content: '▲';
            color: #4caf50; /* Green */
            font-size: 14px;
        }}
        th.sort-desc::after {{
            content: '▼';
            color: #f44336; /* Red */
            font-size: 14px;
        }}
        
        .sub-btn.active-sub {{
            background-color: var(--accent-color) !important;
            color: white !important;
            border-color: var(--accent-color) !important;
        }}

        /* Action Buttons (Default View, Sort By) */
        .action-btn {{
            padding: 6px 14px;
            background: transparent; /* Hollow by default */
            border: 1px solid var(--accent-color);
            color: var(--accent-color);
            border-radius: 4px;
            cursor: pointer;
            font-size: 11px;
            font-weight: 600;
            transition: all 0.2s ease;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
        }}

        .action-btn:hover {{
            background-color: rgba(59, 130, 246, 0.1);
            color: var(--accent-color);
            box-shadow: 0 0 8px rgba(59, 130, 246, 0.2);
            transform: translateY(-1px);
        }}

        .action-btn.active-sub {{
            background-color: var(--accent-color) !important; /* Filled when active */
            color: white !important;
            box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
        }}

        .alert-content {{
            flex-grow: 1;
        }}

        .search-container {{
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 10px;
        }}

        .search-container input {{
            margin-bottom: 0;
            padding: 8px 12px;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--border-color);
            border-radius: 4px;
            color: var(--text-color);
            flex-grow: 1;
            max-width: 400px;
        }}

        hr.section-divider {{
            border: 0;
            height: 1px;
            background: var(--border-color);
            margin: 40px 0 20px 0;
        }}

        /* Status Colors */
        .status-yes {{ color: #00c851; font-weight: bold; }}
        .status-no {{ color: #ff4444; font-weight: bold; }}
        body.light-mode .status-yes {{ color: #059669; }}
        body.light-mode .status-no {{ color: #dc2626; }}

        /* Row Highlighting */
        .unused-warn {{ background: rgba(209, 154, 102, 0.05) !important; }}
        .unused-danger {{ background: rgba(224, 108, 117, 0.1) !important; }}
        body.light-mode .unused-warn {{ background: #fffbeb !important; }}
        body.light-mode .unused-danger {{ background: #fee2e2 !important; }}

    </style>
</head>
<body>
    <div class="container" style="position: relative;">
        <button class="theme-toggle" id="theme-toggle" title="Toggle Light/Dark Mode">
            <span id="theme-icon">🌙</span>
        </button>
        <h1>{report_title}</h1>

        <div class="tabs" id="tabs">
            {tab_buttons}
        </div>

        {tab_contents}
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

        // Global Counter Logic
        function updateTableCounters(table) {{
            if (!table) return;
            const tbody = table.querySelector('tbody');
            if (!tbody) return;
            
            const rows = Array.from(tbody.rows);
            // Check if first column is the counter column
            const header = table.querySelector('thead th');
            if (!header || (header.innerText.trim() !== '#' && header.innerText.trim() !== 'No.')) return;

            let count = 0;
            rows.forEach(row => {{
                if (row.style.display !== 'none') {{
                    count++;
                    row.cells[0].innerText = count;
                }}
            }});
        }}

        // Init - Add Original Index to all rows for Reset
        document.addEventListener('DOMContentLoaded', () => {{
            // Auto-Add '#' column if missing in any table
            document.querySelectorAll('table:not(.no-counter)').forEach(table => {{
                const thead = table.querySelector('thead tr');
                if (thead && !['#', 'No.'].includes(thead.cells[0].innerText.trim())) {{
                    // Add Header
                    const th = document.createElement('th');
                    th.innerText = '#';
                    th.className = 'numeric counter-head';
                    th.style.width = '40px';
                    thead.insertBefore(th, thead.firstChild);
                    
                    // Add Cell to each row
                    table.querySelectorAll('tbody tr').forEach(row => {{
                        const td = document.createElement('td');
                        td.className = 'counter-cell';
                        row.insertBefore(td, row.firstChild);
                    }});
                }}
                updateTableCounters(table);
            }});

            document.querySelectorAll('tbody tr').forEach((row, index) => {{
                row.setAttribute('data-original-index', index);
            }});
            
            // Add Reset Button to all search containers
            document.querySelectorAll('.search-container').forEach(container => {{
                // Check if it's a table container (has input) and allows reset
                if(container.querySelector('input') && container.getAttribute('data-no-reset') !== 'true') {{
                     const resetBtn = document.createElement('button');
                     resetBtn.innerText = "Default View";
                     resetBtn.className = "action-btn active-sub"; // Start filled
                     resetBtn.style.marginLeft = "5px";
                     resetBtn.onclick = function() {{
                         // Clear all action buttons in the nearest search container or tab parent
                         const container = resetBtn.closest('.search-container');
                         if(container) {{
                             container.querySelectorAll('.action-btn').forEach(b => b.classList.remove('active-sub'));
                         }}
                         resetBtn.classList.add('active-sub');

                         const tabContent = resetBtn.closest('.tab-content, .sub-tab-content');
                         if(tabContent) {{
                             const table = tabContent.querySelector('table');
                             if(table) {{
                                 const tbody = table.querySelector('tbody');
                                 const rows = Array.from(tbody.querySelectorAll('tr'));
                                 rows.sort((a, b) => {{
                                     return a.getAttribute('data-original-index') - b.getAttribute('data-original-index');
                                 }});
                                 rows.forEach(r => tbody.appendChild(r));
                                 
                                 // Clear Headers
                                 table.querySelectorAll('th').forEach(th => {{
                                     th.classList.remove('sort-asc', 'sort-desc');
                                     th.removeAttribute('data-asc');
                                 }});
                             }}
                         }}
                     }};
                     
                     // Append next to input
                     container.appendChild(resetBtn);
                }}
            }});
        }});

        function openTab(evt, tabName) {{
            var i, tabContent, tabBtns;
            
            tabContent = document.getElementsByClassName("tab-content");
            for (i = 0; i < tabContent.length; i++) {{
                tabContent[i].style.display = "none";
                tabContent[i].classList.remove("active");
            }}

            tabBtns = document.getElementsByClassName("tab-btn");
            // Only top level buttons - filter by parent?
            // "tab-btn" class is used for sub-tabs too. 
            // We need to distinguish strictly top level by ID or parent.
            const tabsContainer = document.getElementById("tabs");
            const mainBtns = Array.from(document.getElementsByClassName("tab-btn"))
                                  .filter(btn => btn.parentElement === tabsContainer);
                                  
            for (i = 0; i < mainBtns.length; i++) {{
                mainBtns[i].className = mainBtns[i].className.replace(" active", "");
            }}

            document.getElementById(tabName).style.display = "block";
            
            // Trigger reflow
            void document.getElementById(tabName).offsetWidth;
            document.getElementById(tabName).classList.add("active");
            
            evt.currentTarget.className += " active";
        }}
        
        function openSubTab(evt, viewId, parentId) {{
            const btn = evt.currentTarget;
            const container = btn.closest('.search-container');
            const parent = document.getElementById(parentId);
            
            // Hide all sub-contents
            parent.querySelectorAll('.sub-tab-content').forEach(el => el.style.display = 'none');
            
            // Show target
            document.getElementById(viewId).style.display = 'block';
            
            // Update Buttons in the container
            if(container) {{
                container.querySelectorAll('.action-btn').forEach(b => b.classList.remove('active-sub'));
            }}
            btn.classList.add('active-sub');
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
            
             // Simple Filter
             nodes.forEach(node => {{
                 if(node.innerText.toLowerCase().includes(term)) {{
                     node.style.display = "";
                 }} else {{
                     node.style.display = "none";
                 }}
             }});
        }}
        
        function filterTable(tableId, colIndex, term) {{
            const table = document.getElementById(tableId);
            if (!table) return;
            const rows = Array.from(table.getElementsByTagName('tr'));
            term = term.toLowerCase();
            
            // Skip header (i=0)
            for(let i=1; i < rows.length; i++) {{
                // Skip pinned rows
                if (rows[i].getAttribute('data-pinned') === 'true') continue;
                
                let matches = false;
                if (colIndex === -1) {{
                     // Search all columns
                     matches = rows[i].innerText.toLowerCase().includes(term);
                }} else {{
                     // If we have a counter column at 0 and they asked for 0, they likely want the original first data column (now at 1)
                     let actualIdx = colIndex;
                     const header = table.querySelector('thead th');
                     if (header && ['#', 'No.'].includes(header.innerText.trim())) {{
                          actualIdx = colIndex + 1;
                     }}
                     
                     if (actualIdx < rows[i].cells.length) {{
                          matches = rows[i].cells[actualIdx].innerText.toLowerCase().includes(term);
                     }} else {{
                          // Fallback to searching everything if index is out of bounds
                          matches = rows[i].innerText.toLowerCase().includes(term);
                     }}
                }}
                
                rows[i].style.display = matches ? "" : "none";
            }}
            updateTableCounters(table);
        }}

        // Sortable Table Script via Event Delegation
        document.addEventListener('click', (e) => {{
            const th = e.target.closest('th');
            if (!th) return;
            
            const table = th.closest('table');
            if (!table) return;
            
            // Search for the container in the nearest tab-content root
            const tabRoot = table.closest('.tab-content');
            const container = tabRoot ? tabRoot.querySelector('.search-container') : null;
            
            // When sorting by column, clear all 'active' buttons (Resource Size, Default View etc)
            if(container) {{
                container.querySelectorAll('.action-btn').forEach(b => b.classList.remove('active-sub'));
            }}

            const tbody = table.querySelector('tbody');
            if (!tbody) return;
            
            const allRows = Array.from(tbody.querySelectorAll('tr'));
            const rows = allRows.filter(r => r.getAttribute('data-pinned') !== 'true');
            const pinnedRows = allRows.filter(r => r.getAttribute('data-pinned') === 'true');
            const index = Array.from(th.parentNode.children).indexOf(th);
            
            // Detect Number column vs String
            const isNumeric = th.classList.contains('numeric') || 
                            th.classList.contains('counter-head') ||
                            (rows.length > 0 && /[\d\.,]+\s*(B|KB|MB|GB|TB)/i.test(rows[0].children[index].innerText));
                            
            const asc = th.getAttribute('data-asc') !== 'true'; // Toggle
            
            // Reset other headers
            table.querySelectorAll('th').forEach(h => {{
                 h.classList.remove('sort-asc', 'sort-desc');
                 if(h !== th) h.removeAttribute('data-asc');
            }});
            
            th.classList.toggle('sort-asc', asc);
            th.classList.toggle('sort-desc', !asc);
            
            function parseSizeToBytes(val) {{
                val = val.replace(/,/g, '').toLowerCase().trim();
                const match = val.match(/^([\d\.]+)\s*([a-z]+)?/);
                if (!match) return 0;
                const num = parseFloat(match[1]);
                const unit = match[2] || "";
                if (unit.startsWith('k')) return num * 1024;
                if (unit.startsWith('m')) return num * 1024 * 1024;
                if (unit.startsWith('g')) return num * 1024 * 1024 * 1024;
                if (unit.startsWith('t')) return num * 1024 * 1024 * 1024 * 1024;
                return num;
            }}

            rows.sort((a, b) => {{
                const aVal = a.children[index].innerText.trim();
                const bVal = b.children[index].innerText.trim();
                
                if(isNumeric) {{
                    const aNum = parseSizeToBytes(aVal);
                    const bNum = parseSizeToBytes(bVal);
                    return (aNum - bNum) * (asc ? 1 : -1);
                }} else {{
                    return aVal.localeCompare(bVal) * (asc ? 1 : -1);
                }}
            }});
            
            // Re-append pinned rows first, then sorted rows
            pinnedRows.forEach(row => tbody.appendChild(row));
            rows.forEach(row => tbody.appendChild(row));
            th.setAttribute('data-asc', asc);
            
            updateTableCounters(table);
        }});

        // Scroll to Top
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
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
            z-index: 1000;
            transition: opacity 0.3s;
        `;
        scrollBtn.onclick = () => window.scrollTo({{top: 0, behavior: 'smooth'}});
        document.body.appendChild(scrollBtn);

        window.onscroll = () => {{
            if (document.body.scrollTop > 200 || document.documentElement.scrollTop > 200) {{
                scrollBtn.style.display = "block";
            }} else {{
                scrollBtn.style.display = "none";
            }}
        }};

        // Expand/Collapse All
        function expandAll(containerId) {{
            const container = document.getElementById(containerId);
            container.querySelectorAll('details').forEach(d => d.open = true);
        }}

        function collapseAll(containerId) {{
            const container = document.getElementById(containerId);
            container.querySelectorAll('details').forEach(d => d.open = false);
        }}
    </script>
</body>
</html>
"""
