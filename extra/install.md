# Installing PlanExe

This guide explains how to get PlanExe up and running.

## Minimal install on macOS or Linux

Clone this repo, then install and activate a virtual environment. Finally, install the required packages:

```bash
git clone https://github.com/neoneye/PlanExe.git
cd PlanExe
python3 -m venv venv
source venv/bin/activate
(venv) pip install .[gradio-ui]
(venv) python -m src.plan.app_text2plan
```

## Minimal install on Windows

Clone this repo, then install and activate a virtual environment. Finally, install the required packages:

```bash
git clone https://github.com/neoneye/PlanExe.git
cd PlanExe
python3 -m venv venv
.venv\Scripts\activate
(venv) pip install .[gradio-ui]
(venv) python -m src.plan.app_text2plan
```
