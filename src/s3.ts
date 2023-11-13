import * as path from "node:path";
import * as fs from "node:fs/promises";
import * as zlib from "node:zlib";
import { output_dir_path } from "./util.js";
import {
  CSV_FILENAME,
  GZIP_CSV_FILENAME,
  OUTPUT_DIR,
  S3_BUCKET,
} from "./constants.js";
import { Event } from "./types.js";
import { S3Client, PutObjectCommand, PutObjectCommandInput } from "@aws-sdk/client-s3";

const client = new S3Client(config);

export const writeToS3 = async (event: Event) => {
  const dirname = output_dir_path(
    OUTPUT_DIR,
    event.route_id,
    event.direction_id,
    event.stop_id,
    event.event_time
  );
  const pathname = path.join(dirname, CSV_FILENAME);

  const fileContent = await fs.readFile(pathname);
  const compressedFileContentBuffer = zlib.gzipSync(fileContent);

  const s3Params: PutObjectCommandInput = {
    Bucket: S3_BUCKET,
    Body: compressedFileContentBuffer,
    Key: GZIP_CSV_FILENAME,
    ContentType: "text/csv",
    ContentEncoding: "gzip",
  };

  const command = new PutObjectCommand(s3Params);
  return await client.send(command);
};
