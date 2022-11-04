import sys
import bencodepy
import os
from datetime import datetime
from hashlib import sha1
import requests
import struct
from socket import *
import bitstring
import time
import random

torrent_file_path = sys.argv[1]
torrent = bencodepy.decode_from_file(torrent_file_path)
tracker_url = torrent[b'announce']
info = bencodepy.encode(torrent[b'info'])
info_hash = sha1(info).digest()

# Making a peer id
# peer_id_sha = sha1()
# peer_id_sha.update(str(os.getpid()).encode())
# peer_id_sha.update(str(datetime.now()).encode())
# peer_id = peer_id_sha.digest()
peer_id = ('-PC0001-' + ''.join([str(random.randint(0, 9)) for i in range(12)])).encode()

port = 6881

uploaded = 0
downloaded = 0
params = {
    'info_hash': info_hash,
    'peer_id': peer_id,
    'port': 6884,
    'uploaded': uploaded,
    'downloaded': downloaded,
    'left': torrent[b'info'][b'length'] - downloaded,
    'compact': 1,
    'event': 'started'
}

def get_peers(response):
    peers = response[b'peers']
    print(type(peers))

connection_id = 0x41727101980
# connect
action = 0x0
transaction_id = int(random.randrange(0, 255))

# Choose a random transaction_id
def connection_upload_udp(connection_id, action, transaction_id):
    payload = struct.pack("!q", connection_id)
    payload += struct.pack("!i", action)
    payload += struct.pack("!i", transaction_id)
    return payload

# res = requests.get(tracker_url, params)
# raw_res = bencodepy.decode(res.content)

tracker_url = tracker_url.decode("unicode_escape")

def parse_udp_tracker_url(tracker_url):
    domain_url = tracker_url[6:].split(':')
    udp_tracker_url = domain_url[0]
    udp_tracker_port = int(domain_url[1].split('/')[0])
    return (udp_tracker_url, udp_tracker_port)

# print(parse_udp_tracker_url(tracker_url))
url, port = parse_udp_tracker_url(tracker_url)

# url = tracker_url.split(":")
# rem = url[2].split("/")
# port = int(rem[0])
# actual_url = url[0]+":"+url[1]

tracker_sock = socket(AF_INET, SOCK_DGRAM)
tracker_sock.settimeout(10)
conn_payload = connection_upload_udp(connection_id, action, transaction_id)
tracker_sock.sendto(conn_payload, (url, port))

"""
    Receive the packet.
    Check whether the packet is at least 16 bytes.
    Check whether the action is connect.
    Check whether the transaction ID is equal to the one you chose.
    Store the connection ID for future use.
"""
raw_conn_data, conn = tracker_sock.recvfrom(2048)
print(len(raw_conn_data))
if (len(raw_conn_data) < 16):
    print("That's wrong")
    raise NotImplementedError()
else:
    # action
    action = struct.unpack_from("!i", raw_conn_data, 0)[0]
    if (action!=0x0):
        print("Error: action didn't match expected value in 0")
    # transaction_id
    tid = struct.unpack_from("!i", raw_conn_data, 4)[0]
    if (tid!=transaction_id):
        print("Error: transaction ids did not match")
    # connection_id
    cid = struct.unpack_from("!q", raw_conn_data, 8)[0]

    print(action, tid, cid)

"""
    Choose a random transaction ID.
    Fill the announce request structure.
    Send the packet.
"""
# POTENTIAL PROBLEM
transaction_id = random.randrange(0,255)

print(params["left"])

keys = {
    "connection_id": cid,
    "transaction_id": transaction_id,
    "action": action,
    "info_hash": info_hash,
    "peer_id": peer_id,
    "downloaded": downloaded,
    "uploaded": uploaded,
    "left": params["left"],
    "event": 0x2,
    "IP": 0x0,
    "port": port
}

def create_announce_payload(cid, action, transaction_id):
    action = 0x1
    event = 0x2
    IP = 0x0
    for key in keys:
        print(keys[key])
    print()
    payload = struct.pack("!q", cid)
    payload += struct.pack("!i", action)
    payload += struct.pack("!i", transaction_id)
    payload += struct.pack("!20s", info_hash)
    payload += struct.pack("!20s", peer_id)
    payload += struct.pack("!q", downloaded)
    payload += struct.pack("!q", params["left"])
    payload += struct.pack("!q", uploaded)
    payload += struct.pack("!i", event)
    payload += struct.pack("!i", IP)
    payload += struct.pack("!i", random.randint(0,255))
    payload += struct.pack("!i", -1)
    payload += struct.pack("!H", port)
    return payload

announce_payload = create_announce_payload(cid, action, transaction_id)
print(announce_payload)

"""
    Receive the packet.
    Check whether the packet is at least 20 bytes.
    Check whether the transaction ID is equal to the one you chose.
    Check whether the action is announce.
    Do not announce again until interval seconds have passed or an event has occurred.
"""

raw_announce_data, conn = tracker_sock.recvfrom(2048)
print(len(raw_announce_data))
print(raw_announce_data)
if (len(raw_announce_data)<20):
    print("That's wrong")
    raise NotImplementedError()
else:
    # action
    action = struct.unpack_from("!i", raw_announce_data, 0)[0]
    print(action)
    if (action!=0x1):
        print("Error: action didn't match expected value in 0")
    # transaction_id
    tid = struct.unpack_from("!i", raw_announce_data, 4)[0]
    if (tid!=transaction_id):
        print("Error: transaction ids did not match")
    # interval
    interval = struct.unpack_from("!i", raw_announce_data, 8)[0]
    leechers = struct.unpack_from("!i", raw_announce_data, 12)[0]
    seeders = struct.unpack_from("!i", raw_announce_data, 16)[0]
    peers_list = []
    offset=20
    while(offset != len(raw_announce_data)):
        # first 4 bytes is the peer IP address
        raw_peer_IP = struct.unpack_from("!4s", raw_announce_data, offset)[0]
        peer_IP = ".".join(str(a) for a in raw_peer_IP)
        # next 2 bytes is the peer port address
        peer_port = int(struct.unpack_from("!H", raw_announce_data, offset + 4)[0])
        # append to IP, port tuple to peer list
        peers_list.append((peer_IP, peer_port))
        offset = offset + 6

    print("Done parsing announce data")
    print(peers_list)

# Scrape
# """
#     Choose a random transaction ID.
#     Fill the scrape request structure.
#     Send the packet.
# """
# transaction_id = random.randint(0, 255)
# action = 0x2

# def create_scrape_payload(connection_id, transaction_id, action):
#     payload = struct.pack("!q", connection_id)
#     payload += struct.pack("!i", action)
#     payload += struct.pack("!i", transaction_id)
#     payload += struct.pack("!20s", info_hash)
