#!/usr/bin/env python3
import json
import os
import pandas as pd
from pathlib import Path
from datetime import datetime
import markdown
from typing import Dict, Any, Optional

class PlanExeReport:
    def __init__(self, output_dir: str):
        """Initialize the report generator with the directory containing PlanExe output files."""
        self.output_dir = Path(output_dir)
        self.report_data = {}

    def read_json_file(self, filename: str) -> Optional[Dict[str, Any]]:
        """Read a JSON file and return its contents."""
        try:
            with open(self.output_dir / filename, 'r') as f:
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
            with open(self.output_dir / filename, 'r') as f:
                return f.read()
        except FileNotFoundError:
            print(f"Warning: {filename} not found")
            return None

    def read_csv_file(self, filename: str) -> Optional[pd.DataFrame]:
        """Read a CSV file and return its contents as a pandas DataFrame."""
        try:
            return pd.read_csv(self.output_dir / filename)
        except FileNotFoundError:
            print(f"Warning: {filename} not found")
            return None

    def gather_data(self):
        """Gather data from all important files."""
        # Project Pitch
        pitch_data = self.read_json_file('019-pitch.json')
        if pitch_data:
            self.report_data['pitch'] = pitch_data

        # SWOT Analysis
        swot_md = self.read_markdown_file('009-swot_analysis.md')
        if swot_md:
            self.report_data['swot'] = swot_md

        # Expert Criticism
        expert_md = self.read_markdown_file('013-expert_criticism.md')
        if expert_md:
            self.report_data['expert_criticism'] = expert_md

        # Project Plan
        plan_df = self.read_csv_file('026-wbs_project_level1_and_level2_and_level3.csv')
        if plan_df is not None:
            self.report_data['project_plan'] = plan_df

    def generate_html_report(self) -> str:
        """Generate an HTML report from the gathered data."""
        html_parts = []
        
        # Header
        html_parts.append("""
        <html>
        <head>
            <title>PlanExe Project Report</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; }
                h1 { color: #2c3e50; }
                h2 { color: #34495e; margin-top: 30px; }
                .section { margin: 20px 0; padding: 20px; border: 1px solid #eee; border-radius: 5px; }
                table { border-collapse: collapse; width: 100%; margin: 20px 0; }
                th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                th { background-color: #f5f5f5; }
                tr:nth-child(even) { background-color: #f9f9f9; }
                .timestamp { color: #666; font-size: 0.9em; }
            </style>
        </head>
        <body>
        """)

        # Title and Timestamp
        html_parts.append(f"""
        <h1>PlanExe Project Report</h1>
        <p class="timestamp">Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
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
            html_parts.append(df.to_html(classes='dataframe', index=False))
            html_parts.append("</div>")

        # Footer
        html_parts.append("""
        </body>
        </html>
        """)

        return '\n'.join(html_parts)

    def save_report(self, output_filename: str = 'planexe_report.html'):
        """Generate and save the report."""
        self.gather_data()
        html_report = self.generate_html_report()
        
        output_path = self.output_dir / output_filename
        with open(output_path, 'w') as f:
            f.write(html_report)
        
        print(f"Report generated successfully: {output_path}")
        return output_path

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Generate a report from PlanExe output files')
    parser.add_argument('output_dir', help='Directory containing PlanExe output files')
    parser.add_argument('--output', '-o', default='planexe_report.html',
                       help='Output filename (default: planexe_report.html)')
    
    args = parser.parse_args()
    
    report_generator = PlanExeReport(args.output_dir)
    report_path = report_generator.save_report(args.output)
    
    # Try to open the report in the default browser
    try:
        import webbrowser
        webbrowser.open(f'file://{report_path.absolute()}')
    except Exception as e:
        print(f"Could not open browser automatically: {e}")

if __name__ == "__main__":
    main() 