from enum import Enum

class SpeedVsDetailEnum(str, Enum):
    # Production mode.
    ALL_DETAILS_BUT_SLOW = "all_details_but_slow"

    # Developer mode that does a quick check if the pipeline runs. The accuracy is not a priority.
    FAST_BUT_SKIP_DETAILS = "fast_but_skip_details"
