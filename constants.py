from typing import Final

# TODO: not actually final, move from constants to nestor-dl as global?
OUTPUT_DIR: str = './nestor-dl-out'

BASE_URL: Final[str] = "https://nestor.rug.nl"
BLACKBOARD_COLLAB_TOOL_ID: Final[str] = "_4680_1"
BB_BASE_URL: Final[str] = "https://eu-lti.bbcollab.com"
BB_API_REC_PATH: Final[str] = "/collab/api/csa/recordings/"
REQ_NUM_RETRIES: Final[int] = 3  # Number of times a request will retry
REQ_TIMEOUT: Final[float] = 20.0  # request timeout time in seconds
