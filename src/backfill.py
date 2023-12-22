import csv
import glob
import pandas as pd
import boto3
import time

from disk import DATA_DIR, CSV_FIELDS
from s3_upload import _compress_and_upload_file

# deployed 12-17
LOCAL_DATA = str(DATA_DIR / "*/Year=2023/Month=12/Day=[0-9]/events.csv")
FILES = glob.glob(LOCAL_DATA)
FILES_EVENTS = []

# add header if it doesnt exist
for file in FILES:
    print(file)
    with open(file, "r") as f:
        maybe_header = f.readline()
    if "service_date" not in maybe_header:
        with open(file, "r") as f:
            all_events = f.read()
            FILES_EVENTS.append(pd.read_csv(file, names=CSV_FIELDS, index_col=False))
        with open(file, "w") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
            writer.writeheader()
        with open(file, "a") as f:
            f.write(all_events)

# verify that the data is saved
written_dfs = [pd.read_csv(f, index_col=False) for f in FILES]
for og_df, new_df in zip(FILES_EVENTS, written_dfs):
    pd.testing.assert_frame_equal(og_df, new_df)


# upload to s3
s3 = boto3.client("s3")
start_time = time.time()
print("Beginning upload of old events to s3.")
# upload them to s3, gzipped
for fp in FILES:
    _compress_and_upload_file(fp)
end_time = time.time()
print(f"Uploaded {len(FILES)} files to s3, took {end_time - start_time} seconds.")
