# Installing PlanExe for developers

I assume that you are a python developer.

- The `Gradio` UI is primary UI for PlanExe. This is the recommended way to use PlanExe.
- The `Flask` UI is a new UI that I'm making for PlanExe. It's work in progress and is currently less capable than the `Gradio` UI.

### Step 1 - Clone repo

```bash
git clone https://github.com/neoneye/PlanExe.git
```

### Step 2 - Create and activate a virtual environment.

You have multiple options.

#### Option 2A - macOS or Linux

```bash
cd PlanExe
python3 -m venv venv
source venv/bin/activate
```

#### Option 2B - Windows

```bash
cd PlanExe
python3 -m venv venv
.venv\Scripts\activate
```

### Step 3 - Install PlanExe's UI

You have multiple options.

#### Option 3A - Install Gradio UI

```bash
(venv) pip install '.[gradio-ui]'
```

#### Option 3B - Install Flask UI

```bash
(venv) pip install '.[flask-ui]'
```

#### Option 3C - Install everything for non-developers

```bash
(venv) pip install '.[gradio-ui,flask-ui]'
```

#### Option 3D - Install everything for a developer

```bash
(venv) pip install -e '.[gradio-ui,flask-ui]'
```

### Step 4 - Running PlanExe

#### Option 4A - Using PlanExe's Gradio UI

```bash
(venv) python -m planexe.plan.app_text2plan
```

Follow any on-screen instructions or open the specified URL in your web browser.

#### Option 4B - Using PlanExe's Flask UI

```bash
(venv) python -m planexe.ui_flask.app
```

Follow any on-screen instructions or open the specified URL in your web browser.
