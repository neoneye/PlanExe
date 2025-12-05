# PlanExe (frontend_gradio service)

This directory contains the PlanExe Gradio frontend. The shared `planexe` code now lives in `../worker_plan`, so install dependencies with `pip install ./worker_plan[gradio-ui]` and run the UI with `python frontend_gradio/app_text2plan.py` (pointing it at the worker via `WORKER_PLAN_URL`).

The main project README lives one level up at `../README.md`.
