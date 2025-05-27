# PlanExe's new Flask UI - Experimental / Work in progress

Avoid using this for now.

I'm preparing a new UI based on `Flask`. In it's current form it's less powerful than the `Gradio` UI.

The old UI is based on `Gradio` and I have reached the limits of where I can extend it further. The PlanExe `Gradio` UI is a fragile monolith. 
I prefer projects where things are isolated from each other. Where I can make changes one place without it have sideeffects somewhere else. 
It's quick to make things with `Gradio` and it has many nice things that works out of the box.
I'm not going to make more development on the `Gradio` UI.

With the new `Flask` UI, I aim to get rid of the monolithic crap, and keep things separated.
