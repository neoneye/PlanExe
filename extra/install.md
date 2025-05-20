# Installing PlanExe

## Minimal install

Clone this repo, then install and activate a virtual environment. Finally, install the required packages:

```bash
git clone https://github.com/neoneye/PlanExe.git
cd PlanExe
python3 -m venv venv
source venv/bin/activate
(venv) pip install .[gradio-ui]
```

## Advanced install

### Step 1 - Clone repo

```bash
git clone https://github.com/neoneye/PlanExe.git
```

### Step 2 - Create and activate a virtual environment.

```bash
cd PlanExe
python3 -m venv venv
source venv/bin/activate
```

### Step 3A - Install Gradio UI

```bash
(venv) pip install .[gradio-ui]
```

### Step 3B - Install Flask UI

```bash
(venv) pip install .[flask-ui]
```

### Step 3C - Install everything for non-developers

```bash
(venv) pip install .[gradio-ui,flask-ui]
```

### Step 3D - Install everything for a developer

```bash
(venv) pip install -e .[gradio-ui,flask-ui]
```

