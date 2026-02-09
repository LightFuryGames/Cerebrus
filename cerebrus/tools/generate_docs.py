import os
from pathlib import Path

import markdown  # type: ignore


def generate_html_docs():
    """Convert user_guide.md to a standalone HTML file."""

    project_root = Path(__file__).resolve().parent.parent.parent
    md_file = project_root / "docs" / "user_guide.md"
    html_file = project_root / "cerebrus" / "resources" / "user_guide.html"

    # Ensure resources directory exists
    html_file.parent.mkdir(parents=True, exist_ok=True)

    if not md_file.exists():
        print(f"Error: {md_file} not found.")
        return

    with open(md_file, "r", encoding="utf-8") as f:
        text = f.read()

    # Convert Markdown to HTML
    html_content = markdown.markdown(text, extensions=["extra", "toc"])

    # Add CSS styling
    css = """
    <style>
        body { font-family: 'Segoe UI', sans-serif; line-height: 1.6; color: #333; max_width: 800px; margin: 0 auto; padding: 20px; background-color: #f4f4f4; }
        h1, h2, h3 { color: #2c3e50; }
        h1 { border-bottom: 2px solid #3498db; padding-bottom: 10px; }
        h2 { border-bottom: 1px solid #bdc3c7; padding-bottom: 5px; margin-top: 30px; }
        code { background-color: #e0e0e0; padding: 2px 4px; border-radius: 4px; font-family: Consolas, monospace; }
        pre { background-color: #2c3e50; color: #ecf0f1; padding: 15px; border-radius: 5px; overflow-x: auto; }
        a { color: #3498db; text-decoration: none; }
        a:hover { text-decoration: underline; }
        .container { background-color: #fff; padding: 40px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
    </style>
    """

    full_html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Cerebrus User Guide</title>
        {css}
    </head>
    <body>
        <div class="container">
            {html_content}
        </div>
    </body>
    </html>
    """

    with open(html_file, "w", encoding="utf-8") as f:
        f.write(full_html)

    print(f"Successfully generated {html_file}")


if __name__ == "__main__":
    generate_html_docs()
