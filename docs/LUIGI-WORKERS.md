# Luigi Workers Configuration

- Default: workers=1 (sequential, reliable)
- Override: set environment variable LUIGI_WORKERS to an integer >= 1

Examples:
- Windows PowerShell:
  $env:LUIGI_WORKERS = "2"
  # start FastAPI then run a plan
- bash:
  export LUIGI_WORKERS=4

Notes:
- workers=0 disables execution (hang: all tasks remain PENDING)
- >1 uses parallel workers; test carefully (DB connections, filesystem, memory)
- On Windows, multiprocessing uses spawn; ensure all task code is importable and picklable
- Recommended: keep 1 in production; try 2-4 locally if you need parallelism
