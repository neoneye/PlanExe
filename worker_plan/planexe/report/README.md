# PlanExe Report Generator

A tool to generate a beautiful HTML report from PlanExe output files.

## Features

- Combines all important PlanExe output files into a single HTML report
- Includes:
  - Project Pitch
  - SWOT Analysis
  - Expert Criticism
  - Complete Project Plan
- Automatically opens the report in your default web browser
- Responsive design for easy reading
- Clean, professional formatting

## Usage

### Generate report and open in browser
```bash
python -m planexe.report.report_generator /path/to/planexe/output/directory
```

### Generate report without opening it in the browser
```bash
python -m planexe.report.report_generator /path/to/planexe/output/directory --no-browser
```

## Report Contents

The generated report includes:

1. **Project Pitch**
   - Summary of the project
   - Key project points

2. **SWOT Analysis**
   - Strengths
   - Weaknesses
   - Opportunities
   - Threats

3. **Expert Criticism**
   - Detailed feedback from experts
   - Potential issues and considerations

4. **Project Plan**
   - Complete Work Breakdown Structure (WBS)
   - Task dependencies
   - Duration estimates

## Example

If your PlanExe output is in `/home/user/my_project/planexe_dir`, run:
```bash
python -m planexe.report.report_generator /home/user/my_project/planexe_dir
```

This will:
1. Generate a report named `report.html` in the specified directory
2. Automatically open the report in your default web browser

## Troubleshooting

1. **Missing Files**
   - The script will warn you about any missing files
   - The report will still generate with available data

2. **Browser doesn't open**
   - The report is still generated
   - Manually open the HTML file from the output directory

3. **Invalid JSON**
   - Check if the JSON files are properly formatted
   - The script will skip invalid files and continue with valid ones

## Contributing

Feel free to submit issues and enhancement requests! 