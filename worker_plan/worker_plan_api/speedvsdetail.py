from enum import Enum

class SpeedVsDetailEnum(str, Enum):
    ALL_DETAILS_BUT_SLOW = "all_details_but_slow"
    FAST_BUT_SKIP_DETAILS = "fast_but_skip_details"
