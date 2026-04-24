"""
logger.py
────────────────────────────────────────────────
orchestrator_v2 로깅 시스템
────────────────────────────────────────────────
"""

import logging
import sys
from pathlib import Path
from datetime import datetime


def setup_logger(name: str = "orchestrator_v2", log_dir: Path = None) -> logging.Logger:
    """
    로거 설정

    Args:
        name: 로거 이름
        log_dir: 로그 파일 저장 경로

    Returns:
        설정된 Logger 객체
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # 콘솔 핸들러 (INFO 이상만)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # 파일 핸들러 (DEBUG 이상, 모든 수준)
    if log_dir is None:
        log_dir = Path(__file__).parent.parent / "logs"

    log_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"orchestrator_{timestamp}.log"

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        '%(asctime)s [%(name)s] [%(levelname)s] %(funcName)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    logger.debug(f"로거 초기화: {log_file}")
    return logger


# 기본 로거 생성
logger = setup_logger()


class LogStats:
    """로깅 통계"""

    def __init__(self):
        self.stages = {}
        self.errors = []
        self.warnings = []
        self.start_time = datetime.now()

    def log_stage(self, stage_name: str, duration: float, success: bool):
        """스테이지 실행 시간 기록"""
        self.stages[stage_name] = {
            "duration": duration,
            "success": success
        }

    def log_error(self, error_msg: str):
        """에러 기록"""
        self.errors.append(error_msg)
        logger.error(error_msg)

    def log_warning(self, warning_msg: str):
        """경고 기록"""
        self.warnings.append(warning_msg)
        logger.warning(warning_msg)

    def summary(self) -> str:
        """요약 정보"""
        elapsed = (datetime.now() - self.start_time).total_seconds()
        return (
            f"\n{'='*50}\n"
            f"처리 시간: {elapsed:.1f}초\n"
            f"완료 스테이지: {sum(1 for s in self.stages.values() if s['success'])}/{len(self.stages)}\n"
            f"에러: {len(self.errors)}\n"
            f"경고: {len(self.warnings)}\n"
            f"{'='*50}"
        )
