import os
import shutil
import subprocess
from app.utils import logger


def upload_and_cleanup(local_dir: str, date_str: str):
    """
    Uploads local_dir's contents to Google Drive via rclone (if RCLONE_REMOTE
    is configured in .env), then deletes local_dir to free up server disk
    space. Returns the remote path on success, or None if the feature is
    disabled or the upload failed (in which case local files are kept).
    """
    remote_base = os.environ.get("RCLONE_REMOTE", "").strip()
    if not remote_base:
        return None

    year_month = date_str[:7]
    remote_path = f"{remote_base.rstrip('/')}/{year_month}/{date_str}"

    logger.info(f"구글 드라이브 업로드 시작: {local_dir} -> {remote_path}")
    try:
        result = subprocess.run(
            ["rclone", "copy", local_dir, remote_path],
            capture_output=True, text=True
        )
    except FileNotFoundError:
        logger.error("rclone이 설치되어 있지 않습니다. 로컬 파일을 그대로 유지합니다.")
        return None

    if result.returncode != 0:
        logger.error(f"rclone 업로드 실패, 로컬 파일을 그대로 유지합니다: {result.stderr.strip()}")
        return None

    logger.info(f"업로드 성공: {remote_path}")
    shutil.rmtree(local_dir)
    logger.info(f"서버 로컬 파일 삭제 완료: {local_dir}")
    return remote_path
