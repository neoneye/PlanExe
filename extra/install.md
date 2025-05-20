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

## Advanced install

### Step 1 - Clone repo

```bash
git clone https://github.com/neoneye/PlanExe.git
```

### Step 2 - Create and activate a virtual environment.

You have multiple options.

#### Step 2A - macOS or Linux

```bash
cd PlanExe
python3 -m venv venv
source venv/bin/activate
```

#### Step 2B - Windows

```bash
cd PlanExe
python3 -m venv venv
.venv\Scripts\activate
```

### Step 3 - Install PlanExe's UI

You have multiple options.

#### Step 3A - Install Gradio UI

```bash
(venv) pip install .[gradio-ui]
```

#### Step 3B - Install Flask UI

```bash
(venv) pip install .[flask-ui]
```

#### Step 3C - Install everything for non-developers

```bash
(venv) pip install .[gradio-ui,flask-ui]
```

#### Step 3D - Install everything for a developer

```bash
(venv) pip install -e .[gradio-ui,flask-ui]
```

### Step 4 - Running PlanExe

#### Step 4A - Using PlanExe's Gradio UI

```bash
(venv) python -m src.plan.app_text2plan
```

Follow any on-screen instructions or open the specified URL in your web browser.

#### Step 4B - Using PlanExe's Flask UI

```bash
(venv) python -m src.ui_flask.app
```

Follow any on-screen instructions or open the specified URL in your web browser.
