# Worker Plan API

Code shared between `worker_plan_internal`, `worker_plan_database`, `frontend_multi_user`, `frontend_single_user`.

## Best practice

Minimize dependencies on 3rd party packages. Otherwise all the places the `worker_plan_api` is used, will have to include new dependencies. Some of the packages are already incompatible with each other, adding more is likely to make it worse.