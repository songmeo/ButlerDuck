import os
import time

import psycopg2
import logging

logger = logging.getLogger(__name__)

DB_USER = os.environ["DB_USER"]
DB_PASSWORD = os.environ["DB_PASSWORD"]
DB_NAME = os.environ["DB_NAME"]
DB_HOST = os.environ["DB_HOST"]

# This is needed because the DB container takes a longer time to start,
# so the DB may not be available in the beginning.
for _ in range(5):
    try:
        con = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=5432,
        )
        logger.info("Connection successful!")
        break  # success! no need to repeat
    except psycopg2.OperationalError as e:
        logger.error("Error while connecting to the database:", e)
        time.sleep(5)
else:
    logger.error("Can't connect to the database. Abort.")
    exit(1)
