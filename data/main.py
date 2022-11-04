import bencodepy
import random
import hashlib
import urllib.parse
from socket import *
import ssl
import struct
import pprint
import asyncio
import struct
import bitstring

def make_announce_request(final_url,encoded_params,url):
    parsed_url=urllib.parse.urlparse(final_url.decode())
    try:
        host,port=parsed_url.netloc.split(":")
    except ValueError:
        host=parsed_url.netloc
        port=None
    if parsed_url.scheme == 'https' or parsed_url.scheme == 'http':
        client = socket(AF_INET, SOCK_STREAM)

        if parsed_url.scheme == 'https':
            try:
                client.connect((parsed_url.netloc, 443))
            except socket.gaierror:
                raise Exception("Failed while connecting to tracker")
            client = ssl.wrap_socket(client, keyfile=None, certfile=None, server_side=False,
                                        cert_reqs=ssl.CERT_NONE,
                                        ssl_version=ssl.PROTOCOL_SSLv23)
        elif parsed_url.scheme == 'http':
            try:
                client.connect((host, int(port) if port else 80))
            except Exception:
                raise Exception("Failed while connecting to tracker")
        msg = f"GET /announce?{encoded_params} HTTP/1.1\r\nHost: {host}\r\nnConnection: close\r\n\r\n"
        client.send(msg.encode())
        response = b''
        while True:
            data = client.recv(65535)
            if not data:
                client.close()
                break
            response += data

        index = response.find(b'\r\n\r\n')
        if index >= 0:
            return response[index + 4:]
        return response
    elif parsed_url.scheme == 'udp':
        client = socket(AF_INET, SOCK_DGRAM)
        transaction_id = random.getrandbits(16)
        msg = struct.pack('!qii', 0x41727101980, 0, transaction_id)
        client.sendto(msg, (host, int(port)))
        client.settimeout(10.0)
        while True:
            try:
                data = client.recvfrom(1024)
                break
            except:
                raise Exception("UDP Timeout")
        client.settimeout(120)
        try:
            decoded_data = struct.unpack("!iiq", data[0])
            if int(decoded_data[1]) != int(transaction_id):
                raise Exception("Transaction ID does not match")
            transaction_id = random.getrandbits(16)
            msg = struct.pack('!qii20s20sqqqiiiih', decoded_data[2], 1, transaction_id, url['info_hash'],
                                url['peer_id'].encode(), url['downloaded'], url['left'], url['uploaded'], 0, 0,
                                transaction_id, -1, url['port'])
            client.sendto(msg, (host, int(port)))
            old_time = client.gettimeout()
            client.settimeout(15)
            while True:
                try:
                    announce_data = client.recvfrom(65535)
                    break
                except (Exception,):
                    client.settimeout(15)
                    client.sendto(msg, (host, int(port)))
                    old_time -= 15
                    if old_time < 0:
                        raise Exception("Announce timed out")

            decoded_announce_data = struct.unpack(f"!iiiii{len(announce_data[0]) - 20}s", announce_data[0])
            if transaction_id != decoded_announce_data[1]:
                raise Exception("Transaction ID does not match")
            announce_data_dict = {'complete': decoded_announce_data[4], 'incomplete': decoded_announce_data[3],
                                    'interval': decoded_announce_data[2], 'peers': decoded_announce_data[5]}
            response = bencodepy.encode(announce_data_dict)
            return response
        except Exception as e:
            print('********** Here 1') 
            raise Exception(e)

def peer_conns(response):
    decoded_response=bencodepy.decode(response)
    peers=decoded_response[b'peers']
    offset=0
    peers_list=[]
    while(offset<len(peers)):
        ip_number = struct.unpack_from("!I", peers, offset)[0]
        ip = inet_ntoa(struct.pack("!I", ip_number))
        offset += 4
        port = struct.unpack_from("!H", peers, offset)[0]
        offset += 2
        peers_list.append([ip,port])
    return peers_list
def meta_data(data):
    trackers=[]
    if(b'announce-list' in data.keys()):
        trackers=data[b'announce-list']
    if(b'announce' in data.keys()):
        trackers.append(data[b'announce'])
    peer_id="-VS2003-"+''.join([str(random.randint(0,9)) for _ in range(12)])
    info_hash=hashlib.sha1(bencodepy.encode(data[b'info'])).digest()

    params={
        "info_hash":info_hash,
        "peer_id":peer_id,
        "port":6885,
        "left":data[b'info'][b'length'],
        "uploaded":0,
        "downloaded":0,
        "compact":1
    }
    encoded_params=urllib.parse.urlencode(params)
    for i in range(len(trackers)):
        try:
            response=make_announce_request(trackers[i][0],encoded_params,params)
            # response=bencodepy.decode(response)
            return (peer_conns(response),info_hash,peer_id)
        except Exception as e:
            print('********** Here 2')
            print(e)


def open_file():
    raw_data=''
    with open("ubuntu22.torrent","rb") as f:
        raw_data=bencodepy.decode(f.read())
    peers_list,info_hash,peer_id=meta_data(raw_data)
    return (peers_list,info_hash,peer_id,raw_data)
def start():
    peers_list,info_hash,peer_id,raw_data=open_file()
    return (peers_list,info_hash,peer_id,raw_data)
async def handshake(reader,writer,peer_info):
    msg = struct.pack("!b19sq20s20s", 19, "BitTorrent protocol".encode(), 0, peer_info[7],peer_info[8].encode())

    writer.write(msg)
    await writer.drain()

    resp_buffer = b''
    while len(resp_buffer) < 68:
        resp_buffer += await asyncio.wait_for(reader.read(8192), 5)

    decoded_msg = struct.unpack("!b19sq20s20s", resp_buffer[:68])
    if decoded_msg[3] != peer_info[7]:
        raise Exception("Invalid peer closing connection")
    return resp_buffer[68:]

async def start_messaging(peer_info):
    try:
        reader,writer=await asyncio.open_connection(peer_info[0],peer_info[1])
        resp_buffer=await handshake(reader,writer,peer_info)
        interested_msg = struct.pack("!Ib", 1, 2)
        writer.write(interested_msg)
        peer_info[3]=1
        bitfield=bitstring.BitArray(length=peer_info[-1])
        while True:
            try:
                recv_data = await asyncio.wait_for(reader.read(8192), 1)
                if recv_data:
                    resp_buffer += recv_data
                if len(resp_buffer) > 4:
                    msg_len = struct.unpack("!i", resp_buffer[:4])[0]
                    msg_id = resp_buffer[4]
                    if msg_len == 0:
                        resp_buffer = resp_buffer[4:]
                        continue
                    elif msg_len == 1:
                        if msg_id == 0:
                            peer_info[4] = 1
                        elif msg_id == 1:
                            print("Unchoked")
                            peer_info[4] = 0
                        elif msg_id == 2:
                            peer_info[5] = 1
                        elif msg_id == 3:
                            peer_info[5] = 0
                        resp_buffer = resp_buffer[5:]
                    elif msg_len == 5 and len(resp_buffer) >= 9:
                        if msg_id == 4:
                            piece_index = struct.unpack("!i", resp_buffer[4:9])[0]
                            bitfield.set(1, piece_index)
                            resp_buffer = resp_buffer[9:]
                    elif msg_id == 5:
                        if len(resp_buffer) > 4 + msg_len:
                            recv_bitfield = resp_buffer[5:5 + msg_len]
                            resp_buffer = resp_buffer[4 + msg_len:]
                            bitfield = bitstring.BitArray(recv_bitfield)

                    if peer_info[4] == 0 and peer_info[3] and peer_info[6] == 0:
                        pass
            except (Exception) as e:
                print('********** Here 3') 
                print(e)
                pass

    except Exception as e:
        print('********** Here 4')
        print(e)
        pass
async def message_peers(peers_list,info_hash,peer_id,raw_data):
    piece_queue=asyncio.Queue()
    peers=[[val[0],val[1],1,0,1,0,0,info_hash,peer_id,'',int(len(raw_data[b'info'][b'pieces'])/20)] for val in peers_list]
    await asyncio.gather(*([start_messaging(peer) for peer in peers]))
peers_list,info_hash,peer_id,raw_data=start()

asyncio.run(message_peers(peers_list,info_hash,peer_id,raw_data))





