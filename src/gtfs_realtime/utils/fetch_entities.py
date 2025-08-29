import requests
from google.transit import gtfs_realtime_pb2


def get_entities(self):
    feed = None
    vehicles = None
    try:
        feed = gtfs_realtime_pb2.FeedMessage()
        # TODO: add From and User Agent Headers
        # headers = {
        #     'User-Agent': 'Your App Name/1.0',
        #     'From': 'your_email@example.com'
        # }

        response = requests.get(
            self.url,
            headers=self.headers,
            params=self.query_params,
            verify=self.https_verify,
        )

        feed.ParseFromString(response.content)
    except DecodeError:
        pass
        # logger.warning(f"protobuf decode error for {self.url}, {e}")
    except requests.exceptions.Timeout:
        pass
        # logger.warning(f"Timeout for {self.url}")
        # Maybe set up for a retry, or continue in a retry loop
    except requests.exceptions.TooManyRedirects:
        pass
        # logger.warning(f"Too Many Redirects for {self.url}")
    except requests.exceptions.SSLError:
        pass
        # logger.warning(f"SSL Error for {self.url}")
    except requests.exceptions.RequestException as e:
        # catastrophic error. bail.
        raise SystemExit(e)

    except Exception:
        # TODO: update to be more fine-grained in future
        self.updatetimeout(300)
        # logger.exception(e)
    # Returns list of feed entities
    try:
        if feed:
            # TODO: check if this is the best way to filter out messages
            vehicles = [e for e in feed.entity if e.HasField("vehicle")]
    except Exception as e:
        logger.info(f"message does not have vehicle field {e}")
    if vehicles:
        return vehicles
    else:
        return None
