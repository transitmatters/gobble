import schedule
import time

from s3_upload import upload_todays_events_to_s3

schedule.every(30).minutes.do(upload_todays_events_to_s3)

while True:
    schedule.run_pending()
    time.sleep(1)
