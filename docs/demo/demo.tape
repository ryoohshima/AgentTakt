# VHS recording script for the README demo GIF.
# Regenerate with:  vhs docs/demo/demo.tape   (run from the repo root)
#
# The mouse interactions are not typed here — VHS has no mouse commands.
# demo_driver.py replays them inside the app via Textual's auto_pilot;
# VHS only records the terminal.

Output docs/images/demo.gif

Set FontSize 16
Set Width 1250
Set Height 700
Set Padding 12

# Warm up uv so build/download noise stays out of the recording, and shadow
# `agenttakt` so the on-screen command matches real debug-mode usage while the
# auto-piloted driver actually runs.
Hide
Type "uv run python -c 'import agenttakt'"
Enter
Wait@120s
Type "agenttakt() { uv run python docs/demo/demo_driver.py; }"
Enter
Wait
Type "clear"
Enter
Wait
Show

Type "agenttakt open docs/demo/demo_plan.json"
Enter
Wait+Screen@90s /approved: demo-auth-refactor/
Sleep 3s
