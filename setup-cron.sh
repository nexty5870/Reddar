#!/bin/bash
# Setup cron job for autonomous Reddit Intelligence Agent

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_PATH="$SCRIPT_DIR/logs"

mkdir -p "$LOG_PATH"

# Cron job to run every hour (uses --no-web for headless operation)
# Rotates through focus areas: saas at :00, dev_tools at :20, ai_ml at :40
CRON_SAAS="0 * * * * cd $SCRIPT_DIR && ./run.sh cron saas_opportunities >> $LOG_PATH/cron.log 2>&1"
CRON_DEV="20 * * * * cd $SCRIPT_DIR && ./run.sh cron dev_tools >> $LOG_PATH/cron.log 2>&1"
CRON_AI="40 * * * * cd $SCRIPT_DIR && ./run.sh cron ai_ml >> $LOG_PATH/cron.log 2>&1"

echo "Setting up cron jobs for Reddit Intelligence Agent"
echo ""
echo "Cron entries (rotates focus areas every 20 min):"
echo "  :00 - saas_opportunities"
echo "  :20 - dev_tools"
echo "  :40 - ai_ml"
echo ""

# Remove old reddit-intel jobs and add new ones
(crontab -l 2>/dev/null | grep -v "reddit-intel"; \
 echo "# reddit-intel agent"; \
 echo "$CRON_SAAS"; \
 echo "$CRON_DEV"; \
 echo "$CRON_AI") | crontab -

echo "Done! The agent will scan each focus area every hour."
echo "Logs: $LOG_PATH/cron.log"
echo ""
echo "Commands:"
echo "  crontab -l              # View cron jobs"
echo "  crontab -e              # Edit/remove jobs"
echo "  tail -f $LOG_PATH/cron.log  # Watch logs"
