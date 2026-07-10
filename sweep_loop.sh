#!/bin/bash
# Re-run the giveaway sweep on a loop so newly-posted giveaways get entered
# overnight. Each sweep skips anything already in entered.json.
#
# Launch it (keeps the Mac awake, survives closing this terminal):
#   cd ~/goodreads-giveaways
#   nohup caffeinate -i ./sweep_loop.sh > /dev/null 2>&1 &
#
# Watch progress:   tail -f ~/goodreads-giveaways/sweep.log
# Stop it:          pkill -f sweep_loop.sh
#
# Caveat: on a laptop, keep it plugged in with the lid OPEN — a closed lid
# sleeps the machine regardless of caffeinate, which pauses the loop.

cd "$HOME/goodreads-giveaways" || exit 1
source .venv/bin/activate

INTERVAL="${1:-1800}"   # seconds between sweeps (default 30m; backlog burns faster)

while true; do
  echo "===== sweep started $(date) ====="
  python -u giveaways.py run --live
  echo "===== sweep done $(date); sleeping ${INTERVAL}s =====\n"
  sleep "$INTERVAL"
done >> sweep.log 2>&1
