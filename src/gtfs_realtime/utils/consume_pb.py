from Entity import Entity
import datetime


def consume_pb(self):

    # replace with function from fetch_entities.py
    feed_entities = self.get_entities()

    if len(feed_entities) == 0:
        # logger.warning(f"Empty Protobuf file for {self.url}")
        self.updatetimeout(300)
        # exit out of function
        return

    if len(self.entities) == 0:
        # check if any observations exist, if none create all new objects
        for feed_entity in feed_entities:
            entity = Entity(feed_entity)
            self.entities.append(entity)
    else:
        current_ids = []
        # find and update entity
        for feed_entity in feed_entities:
            entity = self.find_entity(feed_entity.id)
            if entity:
                # check if new direction and old direction are same
                # check if last updated date is equivalent to new date, to prevent duplication
                if entity.updated_at[-1] != datetime.datetime.fromtimestamp(feed_entity.vehicle.timestamp).isoformat():
                    if entity.direction_id == feed_entity.vehicle.trip.direction_id:
                        entity.update(feed_entity)
                        current_ids.append(feed_entity.id)
                    else:
                        # first remove old
                        # this checks to make sure there are at least 2 measurements
                        if len(entity.updated_at) > 1:
                            logger.info(type(self.s3_bucket))
                            now = datetime.datetime.now()
                            strf_rep = now.strftime("%Y%m%d")
                            entity.savetos3(
                                self.s3_bucket,
                                f"{self.agency}/{strf_rep}/{entity.route_id}",
                            )
                            # entity.save(self.file_path)
                        self.entities.remove(entity)
                        # now create new
                        entity = Entity(feed_entity)
                        self.entities.append(entity)
                        current_ids.append(feed_entity.id)
                else:
                    current_ids.append(feed_entity.id)
        # remove and save finished entities
        old_ids = [e.entity_id for e in self.entities]
        ids_to_remove = [x for x in old_ids if x not in current_ids]
        for id in ids_to_remove:
            # move logic onto object
            entity = self.find_entity(id)
            if entity:
                # call save method
                if len(entity.updated_at) > 1:
                    # logger.info(type(self.s3_bucket))
                    now = datetime.datetime.now()
                    strf_rep = now.strftime("%Y%m%d")
                    entity.savetos3(
                        self.s3_bucket,
                        f"{self.agency}/{strf_rep}/{entity.route_id}",
                    )
                    # entity.save(self.file_path)
                    # logger.debug(f"Saving entity {entity.entity_id} | {self.file_path}")
                # remove from list
                self.entities.remove(entity)
