import bencodepy
import hashlib
import random
import requests
import struct
from socket import *
from peer import Peer
from prettify import generate_heading
import sys
import math
import asyncio
BLOCK_LENGTH = 2**14
import numpy as np

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
            self.file_length=self.raw_data['info'.encode()]['length'.encode()]
            self.piece_length=self.raw_data['info'.encode()]['piece length'.encode()]
            self.file_name=self.raw_data['info'.encode()]['name'.encode()].decode()
            self.pieces_info=self.raw_data['info'.encode()]['pieces'.encode()]
            info_bencoded=bencodepy.encode(self.raw_data['info'.encode()])
            self.info_hash=hashlib.sha1(info_bencoded).digest()
            self.peer_id=''
            self.port=6884
            self.uploaded=0
            self.downloaded=0
            self.left=self.file_length-self.downloaded
            self.no_pieces=math.ceil(self.file_length/self.piece_length)
            self.piece_status=[0]*self.no_pieces
            self.pieces = {}
            self.num_blocks = math.ceil(self.piece_length/BLOCK_LENGTH)
            generate_heading(f"Num blocks: {self.num_blocks}")
            self.create_piece_dict()
            self.downloading_piece = None
            self.state=0 #0 for random first, 1 for rarest first & 2 for endgame
    
    def create_piece_dict(self):
        blocks = {}
        for i in range(self.no_pieces):
            self.pieces[i] = {}
    
    def write_block(self,piece_index,block_offset,block_data,ip,port):
        if(math.ceil(block_offset/2**14)==self.num_blocks-1):
            self.piece_status[piece_index]=1
            self.downloading_piece=None
        self.pieces[piece_index][math.ceil(block_offset/2**14)] = block_data
        if(sum(self.piece_status)==4):
            self.state=1

    def find_next_block(self, piece_index):
        # print("Here")
        # print(self.pieces, piece_index)
        flag = False
        for i in range(self.num_blocks):
            if (i not in self.pieces[piece_index]):
                flag = True
                return (2**14*i,2**14,False)
        if (not(flag)):
            print("don't be here, fool!!!!!!!!!")
            return (0,0,True)
    
    def try_handshake(self,client,peer_index):
        generate_heading(f"Handshaking with ({self.peers[peer_index].ip}, {self.peers[peer_index].port})...")
        a=self.peers[peer_index].send_handshake(client)
        if(a["status"]==0):
            return 0
        generate_heading(f"Sending interested to ({self.peers[peer_index].ip}, {self.peers[peer_index].port})...")
        b=self.peers[peer_index].send_interested(client)
        if(b["status"]==0):
            # print("ergrg")
            return 0
        return 1

    async def start_messaging(self):
        self.create_piece_dict()
        #fill 4 pieces at random first
        generate_heading(f"No. of Peers: {len(self.peers)}")
        await asyncio.gather(*([peer.begin() for peer in self.peers]))

    def get_rarest_piece(self):
        piece_available_freq=np.array([0]*self.no_pieces)
        for peer in self.peers:
            piece_available_freq += peer.present_bits
        min_elems = np.argsort(piece_available_freq)
        # print(min_elems[:3])
        for elem in min_elems:
            if (self.piece_status[elem]):
                continue
            else:
                return elem
        print("I shouldn't have been here")
        
    def get_piece_index(self):
        if (sum(self.piece_status)==self.no_pieces):
            return (None, True)

        if(self.state==0):
            #random first
            if (self.downloading_piece==None):
                while True:
                    piece_index = random.randint(0,self.no_pieces-1)
                    if (self.piece_status[piece_index]):
                        continue
                    else:
                        # generate_heading(f"Piece index: {piece_index}")
                        self.downloading_piece = piece_index
                        break
                return (self.downloading_piece, False)
            else:
                return (self.downloading_piece, False)
        elif(self.state==1):
            #rarest first
            # generate_heading("In rarest first")
            if(self.downloading_piece== None):
                while True:
                    piece_index=self.get_rarest_piece()
                    # generate_heading(f"Piece index: {piece_index}")
                    self.downloading_piece=piece_index
                    break
                return (self.downloading_piece, False)
            else:
                return (self.downloading_piece, False)

    def message_peers(self):
        i=0
        while True and i<len(self.peers):
            try:
                client=socket(AF_INET,SOCK_STREAM)
                client.settimeout(5)
                client.connect((self.peers[i].ip, self.peers[i].port))
                status = self.try_handshake(client, i)
                if status:
                    break
                i+=1
            except (OSError,) as e:
                print(e)
                i += 1
                # if i == len(self.peers):
                #     print("No peers connecting")
                #     return
        # print(self.no_pieces)
        self.peers[i].read_and_write_messages(client)

    def get_peers(self):
        if(self.peer_id==''):
            self.peer_id='VS2083'+str(random.randint(10000000000000, 99999999999999))
        i=0
        params={
            "info_hash":self.info_hash,
            "peer_id":self.peer_id,
            "port":self.port,
            "uploaded":self.uploaded,
            "downloaded":self.downloaded,
            "left":self.left,
            "compact":1,
            'event': 'started',
        }
        self.tracker_urls=list(set(self.tracker_urls))
        responses=[]
        while i<len(self.tracker_urls):
            url=self.tracker_urls[i]
            try:
                announce_response=requests.get(url,params).content
                response_dict=bencodepy.decode(announce_response)
                responses.append(response_dict)
            except Exception as e:
                if(i==len(self.tracker_urls)-1):
                    # print("Could not connect to any peers")
                    exit(1)
            i+=1
        self.peers=[]
        piport=[]
        for response_dict in responses:
            if(type(response_dict[b'peers'])==list):
                for x in response_dict[b'peers']:
                    if((x[b'ip'].decode(),x[b'port']) not in piport):
                        self.peers.append(Peer(self.peer_id,self.info_hash,x[b'ip'].decode(),x[b'port'],self.no_pieces,self.find_next_block,self.write_block,self.get_piece_index))
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
                    if((ip,port) not in piport):
                        self.peers.append(Peer(self.peer_id,self.info_hash,ip,port,self.no_pieces,self.find_next_block,self.write_block,self.get_piece_index))
                        piport.append((ip,port))
        # print(len(self.peers))