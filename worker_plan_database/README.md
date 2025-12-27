# worker_plan_database

Subclass of the `worker_plan` service with database integration.

The loop is like this:
1. It sits idle until there is an incoming task.
2. Then generates a plan.
3. Sends the generated plan to the destination.
4. Goes back to idle.
