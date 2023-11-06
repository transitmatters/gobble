export interface Event {
  service_date: string;
  route_id: string;
  trip_id: string;
  direction_id: number;
  stop_id: string;
  stop_sequence: number;
  vehicle_id: string;
  vehicle_label: string;
  event_type: "DEP"|"ARR";
  event_time: Date;
  scheduled_headway: number;
  scheduled_tt: number;
}

export interface CSVEvent extends Omit<Event, "event_time"> {
  event_time: string;
}

export type TripID = string;

export interface TripState {
  stop_id: string;
  updated_at: Date;
}
