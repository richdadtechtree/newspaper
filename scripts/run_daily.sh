#!/bin/bash
# 매일 아침 cron이 05:30에 한 번 호출한다.
# 성공(오늘 신문 수집 완료)할 때까지, 또는 CUTOFF 시각이 지날 때까지
# INTERVAL_SECONDS 간격으로 계속 재시도한 뒤 스스로 종료한다.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SCRIPT_DIR"

# shellcheck disable=SC1091
source .venv/bin/activate

CUTOFF="07:00"
INTERVAL_SECONDS=300

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $1"
}

while true; do
    python app/main.py
    if [ $? -eq 0 ]; then
        log "성공, 종료합니다."
        exit 0
    fi

    now="$(date +%H:%M)"
    if [[ "$now" > "$CUTOFF" ]]; then
        log "컷오프 시각(${CUTOFF})을 지났습니다. 오늘은 포기하고 종료합니다."
        exit 1
    fi

    log "실패, ${INTERVAL_SECONDS}초 후 재시도합니다."
    sleep "$INTERVAL_SECONDS"
done
