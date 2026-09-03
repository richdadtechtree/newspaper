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

# FORCE_HEADFUL=1로 설정된 화면 없는 서버에서는 Xvfb(가상 디스플레이) 위에서
# 실행해야 headful 모드가 정상 동작한다. xvfb-run이 설치돼 있으면 항상 그걸로
# 감싸서 실행한다 (FORCE_HEADFUL이 꺼져 있으면 아무 영향 없음).
if command -v xvfb-run >/dev/null 2>&1; then
    RUN_CMD="xvfb-run -a python app/main.py"
else
    RUN_CMD="python app/main.py"
fi

while true; do
    $RUN_CMD
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
