import sys
from tracker import Tracker
import asyncio
if __name__=="__main__":
    # print(sys.argv[1])
    torrent_info=Tracker(sys.argv[1])
    torrent_info.get_peers()
    print("Starting...")
    event_loop=asyncio.get_event_loop()
    task=event_loop.create_task(torrent_info.start_messaging())
    try:
        event_loop.run_until_complete(task)
    except asyncio.CancelledError:
        print("Event loop Error")