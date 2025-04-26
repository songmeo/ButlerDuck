import logging

# TODO FIXME: you don't need a separate logger module; these things go into main.py
# Enable logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

# TODO FIXME: create a separate logger object in each Python module
logger = logging.getLogger(__name__)
