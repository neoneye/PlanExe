#!/usr/bin/env python3
"""
Usage:
PROMPT> python -m src.report_generator /path/to/PlanExe_20250216_dir
"""
import json
import os
import pandas as pd
from pathlib import Path
from datetime import datetime
import markdown
from typing import Dict, Any, Optional
import zipfile
import tempfile
import shutil
from src.plan.filenames import FilenameEnum

class PlanExeReport:
    def __init__(self, input_path: str):
        """Initialize the report generator with either a zip file or directory path."""
        self.input_path = Path(input_path)
        self.report_data = {}
        self.temp_dir = None
        self.working_dir = None
        
    def __enter__(self):
        """Set up the working directory, extracting zip if necessary."""
        if self.input_path.is_file() and self.input_path.suffix == '.zip':
            # Create a temporary directory
            self.temp_dir = tempfile.mkdtemp()
            # Extract the zip file
            with zipfile.ZipFile(self.input_path, 'r') as zip_ref:
                zip_ref.extractall(self.temp_dir)
            # Find the actual directory containing the files
            contents = list(Path(self.temp_dir).iterdir())
            self.working_dir = contents[0] if len(contents) == 1 and contents[0].is_dir() else Path(self.temp_dir)
        else:
            self.working_dir = self.input_path
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Clean up temporary directory if it exists."""
        if self.temp_dir:
            shutil.rmtree(self.temp_dir)

    def read_json_file(self, filename: str) -> Optional[Dict[str, Any]]:
        """Read a JSON file and return its contents."""
        try:
            with open(self.working_dir / filename, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Warning: {filename} not found")
            return None
        except json.JSONDecodeError:
            print(f"Warning: {filename} contains invalid JSON")
            return None

    def read_markdown_file(self, filename: str) -> Optional[str]:
        """Read a markdown file and return its contents."""
        try:
            with open(self.working_dir / filename, 'r') as f:
                return f.read()
        except FileNotFoundError:
            print(f"Warning: {filename} not found")
            return None

    def read_csv_file(self, filename: str) -> Optional[pd.DataFrame]:
        """Read a CSV file and return its contents as a pandas DataFrame."""
        try:
            # First try to detect the delimiter by reading the first few lines
            with open(self.working_dir / filename, 'r') as f:
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
                df = pd.read_csv(self.working_dir / filename, delimiter=delimiter)
                return df
            except:
                # If that fails, try with more options
                try:
                    df = pd.read_csv(self.working_dir / filename, delimiter=delimiter, 
                                   on_bad_lines='skip', engine='python')
                    print(f"Warning: Some lines in {filename} were skipped due to parsing errors")
                    return df
                except Exception as e:
                    print(f"Error reading CSV file {filename}: {str(e)}")
                    return None
                
        except FileNotFoundError:
            print(f"Warning: {filename} not found")
            return None
        except Exception as e:
            print(f"Error reading CSV file {filename}: {str(e)}")
            return None

    def gather_data(self):
        """Gather data from all important files."""
        # Project Pitch
        pitch_data = self.read_json_file(FilenameEnum.PITCH.value)
        if pitch_data:
            self.report_data['pitch'] = pitch_data

        # SWOT Analysis
        swot_md = self.read_markdown_file(FilenameEnum.SWOT_MARKDOWN.value)
        if swot_md:
            self.report_data['swot'] = swot_md

        # Expert Criticism
        expert_md = self.read_markdown_file(FilenameEnum.EXPERT_CRITICISM_MARKDOWN.value)
        if expert_md:
            self.report_data['expert_criticism'] = expert_md

        # Project Plan
        plan_df = self.read_csv_file(FilenameEnum.WBS_PROJECT_LEVEL1_AND_LEVEL2_AND_LEVEL3_CSV.value)
        if plan_df is not None:
            # Clean up the dataframe
            # Remove any completely empty rows or columns
            plan_df = plan_df.dropna(how='all', axis=0).dropna(how='all', axis=1)
            self.report_data['project_plan'] = plan_df

    def generate_html_report(self) -> str:
        """Generate an HTML report from the gathered data."""
        html_parts = []
        
        # Header with improved styling
        html_parts.append("""
        <html>
        <head>
            <title>PlanExe Project Report</title>
            <style>
                body { 
                    font-family: Arial, sans-serif; 
                    margin: 40px;
                    line-height: 1.6;
                    color: #333;
                    max-width: 1200px;
                    margin: 0 auto;
                    padding: 20px;
                }
                h1 { 
                    color: #2c3e50;
                    border-bottom: 2px solid #eee;
                    padding-bottom: 10px;
                }
                h2 { 
                    color: #34495e;
                    margin-top: 30px;
                    border-bottom: 1px solid #eee;
                    padding-bottom: 5px;
                }
                .section { 
                    margin: 20px 0;
                    padding: 20px;
                    border: 1px solid #eee;
                    border-radius: 5px;
                    background-color: #fff;
                    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                }
                table { 
                    border-collapse: collapse;
                    width: 100%;
                    margin: 20px 0;
                    font-size: 14px;
                }
                th, td { 
                    border: 1px solid #ddd;
                    padding: 12px 8px;
                    text-align: left;
                }
                th { 
                    background-color: #f5f5f5;
                    font-weight: bold;
                }
                tr:nth-child(even) { 
                    background-color: #f9f9f9;
                }
                tr:hover {
                    background-color: #f5f5f5;
                }
                .timestamp { 
                    color: #666;
                    font-size: 0.9em;
                    margin-bottom: 30px;
                }
                .dataframe {
                    overflow-x: auto;
                    display: block;
                }
                .source-info {
                    color: #666;
                    font-size: 0.9em;
                    margin-top: 10px;
                    font-style: italic;
                }
            </style>
        </head>
        <body>
        """)

        # Title and Timestamp
        html_parts.append(f"""
        <h1>PlanExe Project Report</h1>
        <p class="timestamp">Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p class="source-info">Source: {self.input_path.name}</p>
        """)

        # Project Pitch
        if 'pitch' in self.report_data:
            html_parts.append("""
            <div class="section">
                <h2>Project Pitch</h2>
            """)
            pitch = self.report_data['pitch']
            if isinstance(pitch, dict):
                for key, value in pitch.items():
                    html_parts.append(f"<h3>{key.replace('_', ' ').title()}</h3>")
                    html_parts.append(f"<p>{value}</p>")
            html_parts.append("</div>")

        # SWOT Analysis
        if 'swot' in self.report_data:
            html_parts.append("""
            <div class="section">
                <h2>SWOT Analysis</h2>
            """)
            html_parts.append(markdown.markdown(self.report_data['swot']))
            html_parts.append("</div>")

        # Expert Criticism
        if 'expert_criticism' in self.report_data:
            html_parts.append("""
            <div class="section">
                <h2>Expert Criticism</h2>
            """)
            html_parts.append(markdown.markdown(self.report_data['expert_criticism']))
            html_parts.append("</div>")

        # Project Plan
        if 'project_plan' in self.report_data:
            html_parts.append("""
            <div class="section">
                <h2>Project Plan</h2>
            """)
            df = self.report_data['project_plan']
            html_parts.append(df.to_html(classes='dataframe', index=False, na_rep=''))
            html_parts.append("</div>")

        # Footer
        html_parts.append("""
        </body>
        </html>
        """)

        return '\n'.join(html_parts)

    def save_report(self, output_path: Optional[str] = None) -> Path:
        """Generate and save the report."""
        self.gather_data()
        html_report = self.generate_html_report()
        
        if output_path:
            output_path = Path(output_path).resolve()  # Convert to absolute path
        else:
            # Generate output filename based on input filename
            stem = self.input_path.stem
            if self.input_path.suffix == '.zip':
                stem = stem.split('_')[0]  # Remove timestamp from filename if present
            output_path = self.input_path.parent.resolve() / f"{stem}_report.html"  # Use absolute path
        
        # Create parent directories if they don't exist
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_report)
        
        print(f"Report generated successfully: {output_path}")
        return output_path

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Generate a report from PlanExe output (zip file or directory)')
    parser.add_argument('input_path', help='Path to PlanExe output zip file or directory')
    parser.add_argument('--output', '-o', help='Output filename (optional)')
    parser.add_argument('--no-browser', action='store_true', help='Do not open browser automatically')
    
    args = parser.parse_args()
    
    # Convert input path to absolute path
    input_path = Path(args.input_path).resolve()
    
    if not input_path.exists():
        print(f"Error: Input path does not exist: {input_path}")
        return
    
    with PlanExeReport(input_path) as report_generator:
        report_path = report_generator.save_report(args.output)
        
        if not args.no_browser:
            # Try to open the report in the default browser
            try:
                import webbrowser
                url = f'file://{report_path.absolute()}'
                print(f"Opening report in browser: {url}")
                if not webbrowser.open(url):
                    print(f"Could not open browser automatically.")
                    print(f"Please open this file in your web browser:")
                    print(f"  {report_path}")
            except Exception as e:
                print(f"Error opening browser: {e}")
                print(f"Please open this file in your web browser:")
                print(f"  {report_path}")

if __name__ == "__main__":
    main() 