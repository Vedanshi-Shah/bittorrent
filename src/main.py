import sys
from tracker import Tracker
if __name__=="__main__":
    # print(sys.argv[1])
    torrent_info=Tracker(sys.argv[1])
    torrent_info.get_peers()
    torrent_info.message_peers()
