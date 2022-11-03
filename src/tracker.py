import bencodepy
import hashlib
import random
import requests
import struct
from socket import *
from peer import Peer
class Tracker:
    def __init__(self,filename):
        self.filename='../torrent_files/'+filename
        with open(self.filename, "rb") as f:
            self.raw_data = bencodepy.decode(f.read())
            self.tracker_urls=[]
            if('announce-list'.encode() in self.raw_data.keys()):
                for u in self.raw_data['announce-list'.encode()]:
                    self.tracker_urls.append(u[0].decode())
            if('announce'.encode() in self.raw_data.keys()):
                self.tracker_urls.append(self.raw_data['announce'.encode()].decode())
            if('length'.encode() in self.raw_data['info'.encode()].keys()):
                self.file_length=self.raw_data['info'.encode()]['length'.encode()]
            else:
                self.file_length=self.raw_data['info'.encode()]['piece length'.encode()]
            self.file_name=self.raw_data['info'.encode()]['name'.encode()].decode()
            self.pieces=self.raw_data['info'.encode()]['pieces'.encode()]
            info_bencoded=bencodepy.encode(self.raw_data['info'.encode()])
            self.info_hash=hashlib.sha1(info_bencoded).digest()
            self.peer_id='VS2083'+str(random.randint(10000000000000, 99999999999999))
            self.port=6885
            self.uploaded=0
            self.downloaded=0
            self.left=self.file_length 
    def get_peers(self):
        i=0
        params={
            "info_hash":self.info_hash,
            "peer_id":self.peer_id,
            "port":self.port,
            "uploaded":self.uploaded,
            "downloaded":self.downloaded,
            "left":self.left,
            "compact":1
        }
        self.tracker_urls=list(set(self.tracker_urls))
        responses=[]
        while i<len(self.tracker_urls):
            url=self.tracker_urls[i]
            try:
                print(url)
                announce_response=requests.get(url,params).content
                response_dict=bencodepy.decode(announce_response)
                responses.append(response_dict)
            except Exception as e:
                # print(e)
                  
                if(i==len(self.tracker_urls)):
                    print("Could not connect to any peers")
                    exit(1)
            i+=1
        self.peers=[]
        # print(len(responses))
        piport=[]
        for response_dict in responses:
            if(type(response_dict[b'peers'])==list):
                for x in response_dict[b'peers']:
                    # print(x[b'ip'].decode(),x[b'port'])
                    if((x[b'ip'].decode(),x[b'port']) not in piport):
                        self.peers.append(Peer(self.peer_id,self.info_hash,x[b'ip'].decode(),x[b'port']))
                        piport.append((x[b'ip'].decode(),x[b'port']))

            else:
                p=response_dict[b'peers']
                offset=0
                while offset<len(p):
                    ip_number = struct.unpack_from("!I", p, offset)[0]
                    ip = inet_ntoa(struct.pack("!I", ip_number))
                    offset += 4
                    port = struct.unpack_from("!H", p, offset)[0]
                    offset += 2
                    # print(ip,port)
                    if((ip,port) not in piport):
                        self.peers.append(Peer(self.peer_id,self.info_hash,ip,port))
                        piport.append((ip,port))
        print(len(self.peers))