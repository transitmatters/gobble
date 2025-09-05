import time
from VehiclePositionFeed import VehiclePositionFeed
from logger import set_up_logging
from config import CONFIG
from consume_pb import consume_pb


logger = set_up_logging(__name__)

if __name__ == "__main__":
    # rt_feed = CONFIG["rt_feeds"]
    rt_feeds = [
        {
            "feed_url": "https://bustracker.pvta.com/infopoint/GTFS-Realtime.ashx?Type=VehiclePosition",
            "agency": "Pioneer Valley Transit Authority",
            "static": "http://www.pvta.com/g_trans/google_transit.zip",
            "config": {},
        },
        {
            "feed_url": "https://meva.syncromatics.com/gtfs-rt/vehiclepositions",
            "agency": "Merrimack Valley Regional Transit Authority",
            "static": "https://data.trilliumtransit.com/gtfs/merrimackvalley-ma-us/merrimackvalley-ma-us.zip",
            "config": {},
        },
        {
            "feed_url": "https://www3.septa.org/gtfsrt/septarail-pa-us/Vehicle/rtVehiclePosition.pb",
            "agency": "SEPTA Regional Rail",
            "config": {},
        },
        {
            "feed_url": "https://www3.septa.org/gtfsrt/septa-pa-us/Vehicle/rtVehiclePosition.pb",
            "agency": "SEPTA Bus Trolley",
            "config": {},
        },
        {
            "feed_url": "https://gtfs-rt.gcrta.vontascloud.com/TMGTFSRealTimeWebService/Vehicle/VehiclePositions.pb",
            "agency": "Cleveland RTA",
            "config": {},
        },
        {
            "config": {},
            "agency": "Marin County Transit District MCTD",
            "feed_url": "https://marintransit.net/gtfs-rt/vehiclepositions",
        },
        {
            "config": {},
            "agency": "Merced County Transit The Bus",
            "feed_url": "https://thebuslive.com/gtfs-rt/vehiclepositions",
        },
        {"config": {}, "agency": "Riverside Transit Agency", "feed_url": "https://rtabus.com/gtfsrt/vehicles"},
        {
            "config": {},
            "agency": "Valley Metro",
            "feed_url": "https://app.mecatran.com/utw/ws/gtfsfeed/vehicles/valleymetro?apiKey=4f22263f69671d7f49726c3011333e527368211f",
        },
        {
            "config": {},
            "agency": "Capital Metro",
            "feed_url": "https://data.texas.gov/download/eiei-9rpf/application%2Foctet-stream",
        },
        {
            "config": {},
            "agency": "Regional Transportation District RTD",
            "feed_url": "https://www.rtd-denver.com/files/gtfs-rt/VehiclePosition.pb",
        },
        {
            "config": {},
            "agency": "Metro St Louis",
            "feed_url": "https://www.metrostlouis.org/RealTimeData/StlRealTimeVehicles.pb",
        },
        {
            "config": {},
            "agency": "Metro Transit",
            "feed_url": "https://svc.metrotransit.org/mtgtfs/vehiclepositions.pb",
        },
        {
            "config": {},
            "agency": "Minnesota Valley Transit Authority",
            "feed_url": "https://srv.mvta.com/infoPoint/GTFS-realtime.ashx?Type=VehiclePosition",
        },
        {
            "config": {},
            "agency": "Intercity Transit",
            "feed_url": "https://its.rideralerts.com/InfoPoint/GTFS-Realtime.ashx?Type=VehiclePosition",
        },
        {
            "config": {},
            "agency": "Community Transit",
            "feed_url": "https://s3.amazonaws.com/commtrans-realtime-prod/vehiclepositions.pb",
        },
        {
            "config": {},
            "agency": "Duluth Transit",
            "feed_url": "https://duluthtransit.com/gtfsrt/Vehicle/VehiclePositions.pb",
        },
        {
            "config": {},
            "agency": "Cincinnati Metro",
            "feed_url": "https://tmgtfsprd.sorttrpcloud.com/TMGTFSRealTimeWebService/vehicle/vehiclepositions.pb",
        },
        {
            "config": {},
            "agency": "Metropolitan Atlanta Rapid Transit Authority MARTA",
            "feed_url": "https://gtfs-rt.itsmarta.com/TMGTFSRealTimeWebService/vehicle/vehiclepositions.pb",
        },
        {
            "config": {},
            "agency": "Port Authority of Allegheny County",
            "feed_url": "https://truetime.portauthority.org/gtfsrt-bus/vehicles",
        },
        {
            "config": {},
            "agency": "Massachusetts Bay Transportation Authority MBTA",
            "feed_url": "https://cdn.mbta.com/realtime/VehiclePositions.pb",
        },
        {
            "config": {},
            "agency": "Maryland Transit Administration",
            "feed_url": "https://mdotmta-gtfs-rt.s3.amazonaws.com/MARC+RT/marc.pb",
        },
        {
            "config": {},
            "agency": "Arlington Transit",
            "feed_url": "https://realtime.arlingtontransit.com/gtfsrt/vehicles",
        },
        {
            "config": {},
            "agency": "RochesterGenesee Regional Transportation Authority RGRTA",
            "feed_url": "https://api.rgrta.com/rtgvehicles?key=00e2dbf6b15742febb37d0a1d7d3acd5",
        },
        {
            "config": {},
            "agency": "Tompkins Consolidated Area Transit TCAT",
            "feed_url": "https://realtimetcatbus.availtec.com/InfoPoint/GTFS-Realtime.ashx?&Type=VehiclePosition&serverid=0",
        },
        {
            "config": {},
            "agency": "Beach Cities Transit",
            "feed_url": "https://redondobeachbct.com/gtfs-rt/vehiclepositions",
        },
        {
            "config": {},
            "agency": "Commerce Municipal Bus Lines",
            "feed_url": "https://citycommbus.com/gtfs-rt/vehiclepositions",
        },
        {
            "config": {},
            "agency": "Shreveport Area Transit System SporTran",
            "feed_url": "https://sportranbus.com/gtfs-rt/vehiclepositions",
        },
        {"config": {}, "agency": "Santa Cruz Metro SCMTD", "feed_url": "https://rt.scmetro.org/gtfsrt/vehicles"},
        {
            "config": {},
            "agency": "Des Moines Area Regional Transit Authority DART",
            "feed_url": "https://www.ridedart.com/gtfs/real-time/vehicle-positions",
        },
        {
            "config": {},
            "agency": "King County Metro",
            "feed_url": "https://s3.amazonaws.com/kcm-alerts-realtime-prod/vehiclepositions.pb",
        },
        {
            "config": {},
            "agency": "Stanislaus Regional Transit Authority StanRTA",
            "feed_url": "https://max.availtec.com/InfoPoint/GTFS-Realtime.ashx?Type=VehiclePosition",
        },
        {
            "config": {},
            "agency": "Towson Loop",
            "feed_url": "https://passio3.com/towson/passioTransit/gtfs/realtime/vehiclePositions",
        },
        {
            "config": {},
            "agency": "Mountain Line Transit",
            "feed_url": "https://mountainline.syncromatics.com/gtfs-rt/vehiclepositions",
        },
        {
            "config": {},
            "agency": "Metro Transit  City of Madison",
            "feed_url": "https://metromap.cityofmadison.com/gtfsrt/vehicles",
        },
        {
            "config": {},
            "agency": "Mountain View Transportation Management Association MVgo",
            "feed_url": "https://mtma.tripshot.com/v1/gtfs/realtime/feed/mvgo?types=VehiclePosition",
        },
        {
            "config": {},
            "agency": "Ben Franklin Transit",
            "feed_url": "https://myride.bft.org/Realtime/GTFS_VehiclePositions.pb",
        },
        {
            "config": {},
            "agency": "Milwaukee County Transit System MCTS",
            "feed_url": "https://realtime.ridemcts.com/gtfsrt/vehicles",
        },
        {
            "config": {},
            "agency": "Montebello Bus Lines",
            "feed_url": "https://mbl.rideralerts.com/InfoPoint/GTFS-Realtime.ashx?Type=VehiclePosition",
        },
        {
            "config": {},
            "agency": "Spirit Bus",
            "feed_url": "https://passio3.com/montereyp/passioTransit/gtfs/realtime/vehiclePositions",
        },
        {
            "config": {},
            "agency": "Emery GoRound",
            "feed_url": "https://emerygoround.tripshot.com/v1/gtfs/realtime/feed/egr?types=VehiclePosition",
        },
        {
            "config": {},
            "agency": "Foothill Transit",
            "feed_url": "https://foothill_3rdparty.rideralerts.com/myStop/GTFS-Realtime.ashx?&Type=VehiclePosition&serverid=0",
        },
        {
            "config": {},
            "agency": "Middletown Area Transit",
            "feed_url": "https://passio3.com/9town/passioTransit/gtfs/realtime",
        },
        {
            "config": {},
            "agency": "Sacramento Regional Transit",
            "feed_url": "https://bustime.sacrt.com/gtfsrt/vehicles",
        },
        {
            "config": {},
            "agency": "GoDurham",
            "feed_url": "https://godurham.rideralerts.com/InfoPoint/GTFS-Realtime.ashx?Type=VehiclePosition",
        },
        {
            "config": {},
            "agency": "Indiana County Transit Authority",
            "feed_url": "https://indigobus.availtec.com/InfoPoint/GTFS-Realtime.ashx?Type=VehiclePosition",
        },
        {
            "config": {},
            "agency": "Luzerne County Transportation Authority",
            "feed_url": "https://realtimelctabus.availtec.com/InfoPoint/GTFS-Realtime.ashx?Type=VehiclePosition",
        },
        {
            "config": {},
            "agency": "Antelope Valley Transit Authority",
            "feed_url": "https://track-it.avta.com/InfoPoint/GTFS-Realtime.ashx?Type=VehiclePosition",
        },
        {
            "config": {},
            "agency": "Centre County Transit Authority",
            "feed_url": "https://realtime.catabus.com/infopoint/GTFS-Realtime.ashx?Type=VehiclePosition",
        },
        {
            "config": {},
            "agency": "Santa Ynez Valley Transit",
            "feed_url": "https://lat-long-prototype.wl.r.appspot.com/vehicle-positions.pb?agency=santa-ynez-valley-transit",
        },
        {
            "config": {},
            "agency": "Jefferson Parish Transit",
            "feed_url": "https://jetapp.jptransit.org/gtfsrt/vehicles",
        },
        {
            "config": {},
            "agency": "NCSU Wolfline",
            "feed_url": "https://passio3.com/ncstateuni/passioTransit/gtfs/realtime/vehiclePositions",
        },
        {
            "config": {},
            "agency": "Rochester Institute of Technology",
            "feed_url": "https://passio3.com/ritech/passioTransit/gtfs/realtime/vehiclePositions",
        },
        {
            "config": {},
            "agency": "Shenango Valley Shuttle Service",
            "feed_url": "https://svss.availtec.com/InfoPoint/GTFS-Realtime.ashx?Type=VehiclePosition",
        },
        {
            "config": {},
            "agency": "Palm Tran",
            "feed_url": "https://www.palmtran.org/TripPlanner/GTFS-Realtime.ashx?Type=VehiclePosition",
        },
        {
            "config": {},
            "agency": "Crawford Area Transportation Authority",
            "feed_url": "https://catabus.rideralerts.com/InfoPoint/GTFS-Realtime.ashx?Type=VehiclePosition",
        },
        {
            "config": {},
            "agency": "Kalamazoo Metro Transit",
            "feed_url": "https://trackmybus.kmetro.org/InfoPoint/GTFS-Realtime.ashx?Type=VehiclePosition",
        },
        {
            "config": {},
            "agency": "Modesto Area Express",
            "feed_url": "https://stanrta.rideralerts.com/InfoPoint/GTFS-Realtime.ashx?Type=VehiclePosition",
        },
        {
            "config": {},
            "agency": "Manatee County Area Transit",
            "feed_url": "https://realtimemcat.availtec.com/InfoPoint/GTFS-Realtime.ashx?Type=VehiclePosition",
        },
        {
            "config": {},
            "agency": "Athens Clarke County Transit",
            "feed_url": "https://bustracker.accgov.com/InfoPoint/GTFS-Realtime.ashx?Type=VehiclePosition",
        },
        {
            "config": {},
            "agency": "SunLine Transit Agency",
            "feed_url": "https://infopoint.sunline.org/InfoPoint/GTFS-Realtime.ashx?Type=VehiclePosition",
        },
        {
            "config": {},
            "agency": "Capital Area Transit",
            "feed_url": "https://cat.rideralerts.com/InfoPoint/gtfs-realtime.ashx?type=vehicleposition",
        },
        {
            "config": {},
            "agency": "Alexandria Transit Company",
            "feed_url": "https://realtime.prod.dash.obaweb.org/agency/71/tripUpdates",
        },
        {
            "config": {},
            "agency": "rabbittransit",
            "feed_url": "https://realtime.rabbittransit.org/InfoPoint/GTFS-Realtime.ashx?Type=VehiclePosition",
        },
        {
            "config": {},
            "agency": "Spokane Transit Authority",
            "feed_url": "https://gtfsbridge.spokanetransit.com/realtime/vehicle/VehiclePositions.pb",
        },
        {"config": {}, "agency": "Fairfax Connector", "feed_url": "https://www.fairfaxcounty.gov/gtfsrt/vehicles"},
        {
            "config": {},
            "agency": "Connecticut Department of Transportation ConnDOT",
            "feed_url": "https://cttprdtmgtfs.ctttrpcloud.com/TMGTFSRealTimeWebService/Vehicle/VehiclePositions.pb",
        },
        {
            "config": {},
            "agency": "Altoona Metro Transit",
            "feed_url": "https://amtran.rideralerts.com/InfoPoint/GTFS-Realtime.ashx?Type=VehiclePosition",
        },
        {
            "config": {},
            "agency": "Green Bay Metro",
            "feed_url": "https://gbm.cadavl.com:4435/ProfilGtfsRt2_0RSProducer-GBM/VehiclePosition.pb",
        },
        {
            "config": {},
            "agency": "Skagit Transit",
            "feed_url": "https://strweb.skagittransit.org/GTFS/GTFS_VehiclePositions.pb",
        },
        {
            "config": {},
            "agency": "Freedom Transit",
            "feed_url": "https://freedom.rideralerts.com/InfoPoint/GTFS-Realtime.ashx?Type=VehiclePosition",
        },
        {
            "config": {},
            "agency": "BisMan Transit",
            "feed_url": "https://passio3.com/bisman/passioTransit/gtfs/realtime/vehiclePositions",
        },
        {
            "config": {},
            "agency": "The Rapid",
            "feed_url": "https://connect.ridetherapid.org/infopoint/GTFS-Realtime.ashx?Type=VehiclePosition",
        },
        {
            "config": {},
            "agency": "Muskegon Area Transit System",
            "feed_url": "https://muskegon.connexionz.net/rtt/public/utility/gtfsrealtime.aspx/vehicleposition",
        },
        {
            "config": {},
            "agency": "Concord Kannapolis Area Transit",
            "feed_url": "https://passio3.com/concordk/passioTransit/gtfs/realtime/vehiclePositions",
        },
        {
            "config": {},
            "agency": "Virginia Railway Express",
            "feed_url": "https://gtfs.vre.org/containercdngtfsupload/VehiclePositionFeed",
        },
        {
            "config": {},
            "agency": "North Central Regional Transit District",
            "feed_url": "https://bluebustracker.availtec.com/InfoPoint/GTFS-Realtime.ashx?Type=VehiclePosition",
        },
        {
            "config": {},
            "agency": "Western Reserve Transit Authority",
            "feed_url": "https://myvalleystops.wrtaonline.com/infopoint/GTFS-Realtime.ashx?Type=VehiclePosition",
        },
        {
            "config": {},
            "agency": "Whatcom Transportation Authority",
            "feed_url": "https://bustracker.ridewta.com/gtfsrt/vehicles",
        },
        {
            "config": {},
            "agency": "Santa Barbara Metropolitan Transit District",
            "feed_url": "https://bustracker.sbmtd.gov/gtfsrt/vehicles",
        },
        {
            "config": {},
            "agency": "Bloomington Transit",
            "feed_url": "https://s3.amazonaws.com/etatransit.gtfs/bloomingtontransit.etaspot.net/position_updates.pb",
        },
        {
            "config": {},
            "agency": "Bryce Canyon National Park Shuttle",
            "feed_url": "https://brycecanyonshuttle.com/subscriptions/gtfsrt/vehicles.ashx",
        },
        {
            "config": {},
            "agency": "Missoula Urban Transportation District MUTD",
            "feed_url": "https://bt.mountainline.com/gtfsrt/vehicles",
        },
        {
            "config": {},
            "agency": "Cambria County Transit Authority",
            "feed_url": "https://live.camtranbus.com/InfoPoint/GTFS-Realtime.ashx?Type=VehiclePosition",
        },
        {
            "config": {},
            "agency": "Link Transit",
            "feed_url": "https://link.rideralerts.com/InfoPoint/GTFS-Realtime.ashx?Type=VehiclePosition",
        },
        {
            "config": {},
            "agency": "CityBus of Greater Lafayette Indiana",
            "feed_url": "https://bus.gocitybus.com/GTFSRT/GTFS_VehiclePositions.pb",
        },
        {
            "config": {},
            "agency": "Akron Metro Regional Transit Authority",
            "feed_url": "https://realtimemetro.availtec.com/infopoint/GTFS-Realtime.ashx?&Type=VehiclePosition&serverid=0",
        },
        {
            "config": {},
            "agency": "Norwalk Transit District",
            "feed_url": "https://mystop.norwalktransit.com/InfoPoint/gtfs-realtime.ashx?type=vehicleposition",
        },
        {
            "config": {},
            "agency": "Greater Peoria Mass Transit",
            "feed_url": "https://clk.rideralerts.com/InfoPoint/gtfs-realtime.ashx?type=vehicleposition",
        },
        {
            "config": {},
            "agency": "Butler Transit Authority",
            "feed_url": "https://butlerivl.availtec.com/InfoPoint/GTFS-Realtime.ashx?Type=VehiclePosition",
        },
        {
            "config": {},
            "agency": "Lexington Transit Authority",
            "feed_url": "https://mystop.lextran.com/InfoPoint/GTFS-Realtime.ashx?Type=VehiclePosition",
        },
        {
            "config": {},
            "agency": "Bustang",
            "feed_url": "https://www.rtd-denver.com/files/bustang/gtfs-rt/Bustang_VehiclePosition.pb",
        },
        {
            "config": {},
            "agency": "Norwalk Transit System",
            "feed_url": "https://nts.rideralerts.com/InfoPoint/GTFS-Realtime.ashx?Type=VehiclePosition",
        },
        {
            "config": {},
            "agency": "Racine Transit",
            "feed_url": "https://racine.connexionz.net/rtt/public/utility/gtfsrealtime.aspx/vehicleposition",
        },
        {
            "config": {},
            "agency": "City of Mobile",
            "feed_url": "https://realtimemobile.availtec.com/InfoPoint/GTFS-Realtime.ashx?Type=VehiclePosition",
        },
        {
            "config": {},
            "agency": "Concho Valley Transit District",
            "feed_url": "https://passio3.com/conchovt/passioTransit/gtfs/realtime/vehiclePositions",
        },
        {
            "config": {},
            "agency": "Endless Mountains Transportation Authority",
            "feed_url": "https://best.rideralerts.com/InfoPoint/GTFS-Realtime.ashx?Type=VehiclePosition",
        },
        {
            "config": {},
            "agency": "Fayette Area Coordinated Transportation",
            "feed_url": "https://fact.rideralerts.com/InfoPoint/GTFS-Realtime.ashx?Type=VehiclePosition",
        },
        {
            "config": {},
            "agency": "StarTran",
            "feed_url": "https://startran.connexionz.net/rtt/public/utility/gtfsrealtime.aspx/vehicleposition",
        },
        {
            "config": {},
            "agency": "Lower Anthracite Transit System",
            "feed_url": "https://lats.rideralerts.com/InfoPoint/GTFS-Realtime.ashx?Type=VehiclePosition",
        },
        {
            "config": {},
            "agency": "Westmoreland County Transit Authority",
            "feed_url": "https://wcta.rideralerts.com/InfoPoint/gtfs-realtime.ashx?type=vehicleposition",
        },
        {
            "config": {},
            "agency": "Long Beach Transit",
            "feed_url": "https://lbtgtfs.lbtransit.com/TMGTFSRealTimeWebService/Vehicle/VehiclePositions.pb",
        },
        {
            "config": {},
            "agency": "Mid Mon Valley Transit Authority",
            "feed_url": "https://mmvta.rideralerts.com/InfoPoint/gtfs-realtime.ashx?type=vehicleposition",
        },
        {
            "config": {},
            "agency": "Pioneer Valley Transit Authority",
            "feed_url": "https://bustracker.pvta.com/infopoint/GTFS-Realtime.ashx?Type=VehiclePosition",
        },
        {
            "config": {},
            "agency": "Wichita Transit",
            "feed_url": "https://bus.wichitatransit.org/InfoPoint/GTFS-Realtime.ashx?Type=VehiclePosition",
        },
        {
            "config": {},
            "agency": "City of Jacksonville",
            "feed_url": "https://passio3.com/jacksonville/passioTransit/gtfs/realtime/vehiclePositions",
        },
        {
            "config": {},
            "agency": "Metropolitan Tulsa Transit Authority",
            "feed_url": "https://tulsa.rideralerts.com/InfoPoint/GTFS-Realtime.ashx?Type=VehiclePosition",
        },
        {
            "config": {},
            "agency": "New River Transit Authority",
            "feed_url": "https://passio3.com/beckley/passioTransit/gtfs/realtime/vehiclePositions",
        },
        {
            "config": {},
            "agency": "Berks Area Regional Transportation Authority",
            "feed_url": "https://busfinder.bartabus.com/Infopoint/gtfs-realtime.ashx?type=vehicleposition",
        },
        {
            "config": {},
            "agency": "Lebanon Transit",
            "feed_url": "https://realtime.lebanontransit.org/InfoPoint/gtfs-realtime.ashx?type=vehicleposition",
        },
        {
            "config": {},
            "agency": "Capital Area Transit System",
            "feed_url": "https://cats.rideralerts.com/InfoPoint/gtfs-realtime.ashx?type=vehicleposition",
        },
        {
            "config": {},
            "agency": "Lehigh and Northampton Transportation Authority",
            "feed_url": "https://realtimelanta.availtec.com/InfoPoint/GTFS-Realtime.ashx?Type=VehiclePosition",
        },
        {
            "config": {},
            "agency": "Red Rose Transit Authority",
            "feed_url": "https://busfinder.redrosetransit.com/Infopoint/gtfs-realtime.ashx?type=vehicleposition",
        },
        {
            "config": {},
            "agency": "Ride Gwinnett",
            "feed_url": "https://realtimegwinnett.availtec.com/InfoPoint/gtfs-realtime.ashx?type=vehicleposition",
        },
        {
            "config": {},
            "agency": "Valley Regional Transit",
            "feed_url": "https://www.valleyregionaltransit.org/GTFS/position_updates.pb",
        },
        {
            "config": {},
            "agency": "New Castle Area Transit Authority",
            "feed_url": "https://ncata.rideralerts.com/InfoPoint/GTFS-Realtime.ashx?Type=VehiclePosition",
        },
        {
            "config": {},
            "agency": "County of Lackawanna Transit System",
            "feed_url": "https://coltsivl.availtec.com/InfoPoint/GTFS-Realtime.ashx?Type=VehiclePosition",
        },
        {
            "config": {},
            "agency": "Schuylkill Transportation System",
            "feed_url": "https://sts.rideralerts.com/InfoPoint/GTFS-Realtime.ashx?Type=VehiclePosition",
        },
        {
            "config": {},
            "agency": "Hazleton Public Transit",
            "feed_url": "https://realtimehpts.availtec.com/InfoPoint/GTFS-Realtime.ashx?Type=VehiclePosition",
        },
        {
            "config": {},
            "agency": "Rosemead Explorer",
            "feed_url": "https://passio3.com/rosemead/passioTransit/gtfs/realtime/vehiclePositions",
        },
        {"config": {}, "agency": "Culver CityBus", "feed_url": "https://nextccbus.org/gtfsrt/vehicles"},
        {"config": {}, "agency": "GoRaleigh", "feed_url": "https://www.goraleighlive.org/gtfsrt/vehicles"},
        {
            "config": {},
            "agency": "Lakeland Area Mass Transit District",
            "feed_url": "https://www.ccbusinfo.com/InfoPoint/gtfs-realtime.ashx?type=vehicleposition",
        },
        {
            "config": {},
            "agency": "Area Transit Authority",
            "feed_url": "https://rideata.rideralerts.com/InfoPoint/GTFS-Realtime.ashx?Type=VehiclePosition",
        },
        {
            "config": {},
            "agency": "Maryland Transit Administration",
            "feed_url": "https://mdotmta-gtfs-rt.s3.amazonaws.com/MARC%20RT/marc-vp.pb",
        },
        {
            "config": {},
            "agency": "Billings Metropolitan Transit",
            "feed_url": "https://passio3.com/billings/passioTransit/gtfs/realtime/vehiclePositions",
        },
        {
            "config": {},
            "agency": "Charlotte Area Transit System",
            "feed_url": "https://gtfsrealtime.ridetransit.org/GTFSRealTime/Vehicle/VehiclePositions.pb",
        },
        {
            "config": {},
            "agency": "River Valley Transit",
            "feed_url": "https://my.ridervt.com/InfoPoint/GTFS-Realtime.ashx?Type=VehiclePosition",
        },
        {
            "config": {},
            "agency": "Pottstown Area Rapid Transit",
            "feed_url": "https://part.rideralerts.com/InfoPoint/GTFS-Realtime.ashx?Type=VehiclePosition",
        },
        {
            "config": {},
            "agency": "Yamhill County Transit Area",
            "feed_url": "https://ycta.connexionz.net/rtt/public/utility/gtfsrealtime.aspx/vehicleposition",
        },
        {
            "config": {},
            "agency": "Sarasota County Area Transit",
            "feed_url": "https://breezerider.tripsparkhost.com/gtfs/Realtime/GTFS_VehiclePositions.pb",
        },
        {
            "config": {},
            "agency": "Fresno Area Express",
            "feed_url": "https://gis4u.fresno.gov/TMGTFSRealTimeWebService/Vehicle/VehiclePositions.pb",
        },
        {
            "config": {},
            "agency": "Valley Transit",
            "feed_url": "https://itransitnw.com/rtt/public/utility/gtfsrealtime.aspx/vehicleposition",
        },
        {
            "config": {},
            "agency": "GoCary",
            "feed_url": "https://www.gocarylive.org/gtfs/Realtime/GTFS_VehiclePositions.pb",
        },
        {
            "config": {},
            "agency": "City of Irvine",
            "feed_url": "https://passio3.com/irvine/passioTransit/gtfs/realtime/vehiclePositions",
        },
        {
            "config": {},
            "agency": "Housatonic Area Regional Transit",
            "feed_url": "https://passio3.com/hart/passioTransit/gtfs/realtime/vehiclePositions",
        },
        {
            "config": {},
            "agency": "Research Triangle Regional Public Transportation Authority",
            "feed_url": "https://gotriangle.tripsparkhost.com/gtfs/Realtime/GTFS_VehiclePositions.pb",
        },
        {
            "config": {},
            "agency": "Via Mobility",
            "feed_url": "https://passio3.com/viaboulder/passioTransit/gtfs/realtime/vehiclePositions",
        },
    ]
    VehiclePositionFeeds = []
    for feed in rt_feeds:
        x = VehiclePositionFeed(feed["feed_url"], feed["agency"], timeout=30)
        VehiclePositionFeeds.append(x)
    running = True

    while running:
        for feed in VehiclePositionFeeds:
            consume_pb(feed, {})
        time.sleep(30)
