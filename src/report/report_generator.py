"""
This generates the report and afterwards opens it in the browser.
PROMPT> python -m src.report.report_generator /path/to/PlanExe_20250216_dir

This generates the report without opening the browser.
PROMPT> python -m src.report.report_generator /path/to/PlanExe_20250216_dir --no-browser
"""
import re
import json
import logging
import pandas as pd
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
import markdown
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

@dataclass
class ReportDocumentItem:
    document_title: str
    document_html_content: str

class ReportGenerator:
    def __init__(self):
        self.report_item_list: list[ReportDocumentItem] = []
        
    def read_json_file(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """Read a JSON file and return its contents."""
        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logging.warning(f"{file_path} not found")
            return None
        except json.JSONDecodeError:
            logging.warning(f"{file_path} contains invalid JSON")
            return None

    def read_markdown_file(self, file_path: Path) -> Optional[str]:
        """Read a markdown file and return its contents."""
        try:
            with open(file_path, 'r') as f:
                return f.read()
        except FileNotFoundError:
            logging.warning(f"{file_path} not found")
            return None

    def read_csv_file(self, file_path: Path) -> Optional[pd.DataFrame]:
        """Read a CSV file and return its contents as a pandas DataFrame."""
        try:
            # First try to detect the delimiter by reading the first few lines
            with open(file_path, 'r') as f:
                first_line = f.readline().strip()
                
            # Count potential delimiters
            delimiters = {
                ',': first_line.count(','),
                ';': first_line.count(';'),
                '\t': first_line.count('\t'),
                '|': first_line.count('|')
            }
            
            # Use the delimiter that appears most frequently
            delimiter = max(delimiters.items(), key=lambda x: x[1])[0]
            
            # Try reading with the detected delimiter
            try:
                df = pd.read_csv(file_path, delimiter=delimiter)
                return df
            except:
                # If that fails, try with more options
                try:
                    df = pd.read_csv(file_path, delimiter=delimiter, 
                                   on_bad_lines='skip', engine='python')
                    logging.warning(f"Some lines in {file_path} were skipped due to parsing errors")
                    return df
                except Exception as e:
                    logging.error(f"Error reading CSV file {file_path}: {str(e)}")
                    return None
                
        except FileNotFoundError:
            logging.error(f"{file_path} not found")
            return None
        except Exception as e:
            logging.error(f"Error reading CSV file {file_path}: {str(e)}")
            return None

    def append_markdown(self, document_title: str, file_path: Path):
        """Append a markdown document to the report."""
        md_data = self.read_markdown_file(file_path)
        if md_data is None:
            logging.warning(f"Document: '{document_title}'. Could not read markdown file: {file_path}")
            return
        html = markdown.markdown(md_data)
        self.report_item_list.append(ReportDocumentItem(document_title, html))
    
    def append_csv(self, document_title: str, file_path: Path):
        """Append a CSV to the report."""
        df_data = self.read_csv_file(file_path)
        if df_data is None:
            logging.warning(f"Document: '{document_title}'. Could not read CSV file: {file_path}")
            return
        # Clean up the dataframe
        # Remove any completely empty rows or columns
        df = df_data.dropna(how='all', axis=0).dropna(how='all', axis=1)
        html = df.to_html(classes='dataframe', index=False, na_rep='')
        self.report_item_list.append(ReportDocumentItem(document_title, html))

    def generate_html_report(self) -> str:
        """Generate an HTML report from the gathered data."""

        path_to_template = Path(__file__).parent / 'report_template.html'
        with open(path_to_template, 'r') as f:
            html_template = f.read()
        
        html_parts = []
        # Title and Timestamp
        html_parts.append(f"""
        <h1>PlanExe Project Report</h1>
        <p class="timestamp">Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        """)

        def add_section(title: str, content: str):
            html_parts.append(f"""
            <div class="section">
                <button class="collapsible">{title}</button>
                <div class="content">        
                    {content}
                </div>
            </div>
            """)

        for item in self.report_item_list:
            add_section(item.document_title, item.document_html_content)

        html_content = '\n'.join(html_parts)

        # Replace the content between <!--CONTENT-START--> and <!--CONTENT-END--> with html_content
        pattern = re.compile(r'<!--CONTENT-START-->.*<!--CONTENT-END-->', re.DOTALL)
        html = re.sub(
            pattern,
            f'<!--CONTENT-START-->\n{html_content}\n<!--CONTENT-END-->',
            html_template
        )

        return html

    def save_report(self, output_path: Path) -> None:
        """Generate and save the report."""
        html_report = self.generate_html_report()
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_report)
        
        logger.info(f"Report generated successfully: {output_path}")

def main():
    from src.plan.filenames import FilenameEnum
    import argparse
    parser = argparse.ArgumentParser(description='Generate a report from PlanExe output (zip file or directory)')
    parser.add_argument('input_path', help='Path to PlanExe output zip file or directory')
    parser.add_argument('--no-browser', action='store_true', help='Do not open browser automatically')
    
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler()
        ]
    )

    
    # Convert input path to absolute path
    input_path = Path(args.input_path).resolve()
    
    if not input_path.exists():
        print(f"Error: Input path does not exist: {input_path}")
        return
    
    output_path = input_path / FilenameEnum.REPORT.value
    
    report_generator = ReportGenerator()
    report_generator.append_markdown('Pitch', input_path / FilenameEnum.PITCH_MARKDOWN.value)
    report_generator.append_markdown('Assumptions', input_path / FilenameEnum.CONSOLIDATE_ASSUMPTIONS_MARKDOWN.value)
    report_generator.append_markdown('SWOT Analysis', input_path / FilenameEnum.SWOT_MARKDOWN.value)
    report_generator.append_markdown('Team', input_path / FilenameEnum.TEAM_MARKDOWN.value)
    report_generator.append_markdown('Expert Criticism', input_path / FilenameEnum.EXPERT_CRITICISM_MARKDOWN.value)
    report_generator.append_csv('Work Breakdown Structure', input_path / FilenameEnum.WBS_PROJECT_LEVEL1_AND_LEVEL2_AND_LEVEL3_CSV.value)
    report_generator.save_report(output_path)
        
    if not args.no_browser:
        # Try to open the report in the default browser
        try:
            import webbrowser
            url = f'file://{output_path.absolute()}'
            print(f"Opening report in browser: {url}")
            if not webbrowser.open(url):
                print(f"Could not open browser automatically.")
                print(f"Please open this file in your web browser:")
                print(f"  {output_path}")
        except Exception as e:
            print(f"Error opening browser: {e}")
            print(f"Please open this file in your web browser:")
            print(f"  {output_path}")

if __name__ == "__main__":
    main()