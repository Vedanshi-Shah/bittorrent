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
from Block import Block
import heapq
import time
import aiofiles
import numpy as np
from heapq import nlargest
import os

piport = []
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
            # print(self.raw_data[b'info'][b'length'])
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
            print(self.file_length, self.piece_length, self.file_length/self.piece_length)
            self.no_pieces=math.ceil(self.file_length/self.piece_length)
            self.piece_status=[0]*self.no_pieces
            self.pieces = {}
            self.num_blocks = math.ceil(self.piece_length/BLOCK_LENGTH)
            # generate_heading(f"Num blocks: {self.num_blocks}")
            self.create_piece_dict()
            self.downloading_piece = None
            self.state=0 #0 for random first, 1 for rarest first & 2 for endgame
            # generate_heading(f"No. of Pieces: {self.no_pieces}")
            self.last_piece_length = self.file_length-(self.no_pieces-1)*self.piece_length
            self.num_blocks_last = math.ceil(self.last_piece_length/2**14)
            self.block_heap=[]
            self.get_pieces_hashes()
            print("Last piece length:",self.last_piece_length)
            print("Blocks in last piece:",self.num_blocks_last)
            # self.print_hashes()
            self.create_file()
            self.unchoked_peers = []
            self.download_rates = {}
            self.upload_rates = {}
    
    def create_file(self):
        print(self.file_name)
        with open(self.file_name,"w") as f:
            pass

    def allDownloaded(self):
        # print(self.piece_status)
        if(sum(self.piece_status)==self.no_pieces):
            return True
        return False

    def get_piece_block(self,ip,port):
        # check if all pieces have been receive
        if(sum(self.piece_status)==self.no_pieces):
            return (None,None,None,True)
        
        exp_blocks=[b for b in self.block_heap if b.began_requesting+25<time.time()]
        
        if(len(exp_blocks)>0):#check if any block has expired
            # generate_heading("Picking an expired block")
            i=np.random.randint(0,len(exp_blocks))
            exp_blocks[i].began_requesting=time.time()
            heapq.heapify(self.block_heap)
            return (exp_blocks[i].piece,exp_blocks[i].offset,exp_blocks[i].size)
        else:
            # generate_heading(f"Piece and block number being requested by {ip} | {port}")
            #search for next block
            if(self.downloading_piece==None):
                #choose a piece and request the first block
                while True:
                    piece_index = random.randint(0,self.no_pieces-1)
                    if (self.piece_status[piece_index]):
                        continue
                    elif(sum(self.piece_status)==self.no_pieces):
                        break
                    else:
                        # generate_heading(f"Piece index: {piece_index}")
                        self.downloading_piece = piece_index
                        block_offset,block_size=self.find_next_block(self.downloading_piece)
                        if(block_offset==None):
                            break
                        a=Block(self.downloading_piece,block_offset,block_size)
                        heapq.heappush(self.block_heap,a)
                        print("96:",len(self.block_heap),piece_index,block_offset)
                        heapq.heapify(self.block_heap)
                        self.pieces[self.downloading_piece][math.ceil(block_offset/2**14)]=a
                        return (self.downloading_piece,block_offset,block_size,False)
            else:
                #request the next block of that piece
                block_offset,block_size=self.find_next_block(self.downloading_piece)
                if(block_offset!=None):
                    a=Block(self.downloading_piece,block_offset,block_size)
                    heapq.heappush(self.block_heap,a)
                    print("106:",len(self.block_heap),self.downloading_piece,block_offset)
                    heapq.heapify(self.block_heap)
                    self.pieces[self.downloading_piece][math.ceil(block_offset/2**14)]=a
                    return (self.downloading_piece,block_offset,block_size,False)
            return (None,None,None,False)

    def print_hashes(self):
        for idx,hash in self.hashes.items():
            print(f"{idx} : {hash}")
    
    def get_pieces_hashes(self):
        start = 0
        offset = 20
        self.hashes = {}
        for i in range(self.no_pieces):
            self.hashes[i] = self.pieces_info[start:start+offset]
            start+=offset
    
    def create_piece_dict(self):
        for i in range(self.no_pieces):
            self.pieces[i] = {}
    
    def rerequest_piece(self):
        exp_blocks=[b for b in self.block_heap if b.began_requesting+20<time.time()]
        if(len(exp_blocks)>0):
            i=np.random.randint(0,len(exp_blocks))
            self.block_heap[i].began_requesting=time.time()
            heapq.heapify(self.block_heap)
            return (self.block_heap[i].piece,self.block_heap[i].offset,self.block_heap[i].size,False)
        else:
            print("meow")
            return (None,None,None,True)
    
    def is_piece_complete(self,piece_index):
        count = 0
        for block in self.pieces[piece_index].values():
            if block.data!=b"":
                count += 1
        if (piece_index==self.no_pieces-1 and count==self.num_blocks_last):
            return True
        if (count==self.num_blocks):
            return True
        return False
    
    def verify_piece(self,piece_index):
        my_piece = self.pieces[piece_index]
        data = b""
        for block in my_piece.values():
            data += block.data
        hash = hashlib.sha1(data)
        hash = hash.digest()
        if (hash!=self.hashes[piece_index]):
            self.pieces[piece_index] = {}
            self.piece_status[piece_index] = 0
            # generate_heading("Corrupted piece")
            return False,None
        return True,data
    
    async def write_piece(self,piece_index,data):
        # generate_heading("Piece verified and being written")
        async with aiofiles.open(self.file_name, "rb+") as f:
            pos = piece_index * self.piece_length
            await f.seek(pos, 0)
            await f.write(data)
        # f.close()
    
    async def broadcast_have(self, piece_index):
        generate_heading("Broadcasting have...")
        for peer in self.peers:
            peer.send_have(piece_index)
    
    async def write_block(self,piece_index,block_offset,block_data):
        # if(self.pieces[piece_index][math.ceil(block_offset/2**14)].status==2):
        #     return
        # generate_heading(f"{piece_index} | {block_offset} |")
        # self.pieces[piece_index][math.ceil(block_offset/2**14)]=Block(piece_index,math.ceil(block_offset/2**14),len(block_data))
        self.pieces[piece_index][math.ceil(block_offset/2**14)].data=block_data
        self.pieces[piece_index][math.ceil(block_offset/2**14)].status=2

        if (self.is_piece_complete(piece_index)):
            is_verified,data = self.verify_piece(piece_index)
            if (is_verified):
                # Need to await here
                self.downloading_piece=None
                self.piece_status[piece_index]=1
                self.write_piece(piece_index,data)
                await self.broadcast_have(piece_index)
                # del self.pieces[piece_index]
                generate_heading(f"Number of pieces downloaded: {sum(self.piece_status)}")

        # print("138: meow",len(self.block_heap))
        self.block_heap.remove(self.pieces[piece_index][math.ceil(block_offset/2**14)])
        # print("139: meow",len(self.block_heap))
        heapq.heapify(self.block_heap)
        if(sum(self.piece_status)==4):
            self.state=1
    
    def get_last_piece(self,piece_index):
        i = 0
        for i in range(self.num_blocks_last-1):
            if (i not in self.pieces[piece_index]):
                # a=Block(piece_index,2**14*i,2**14)
                # heapq.heappush(self.block_heap,a)
                # self.pieces[piece_index][i]=a
                return (2**14*i,2**14)
        last_length = self.last_piece_length-(self.num_blocks_last-1)*(2**14)
        if(self.num_blocks_last-1 not in self.pieces[piece_index]):
            # generate_heading(f"Calling the last block for length of {last_length}")
            return (2**14*(self.num_blocks_last-1),last_length)
        # else:
        #     generate_heading("2")
        #     generate_heading(f"{piece_index} {2**14*i} {last_length}")
        #     a=Block(piece_index,2**14*(self.num_blocks_last-1),last_length)
        #     heapq.heappush(self.block_heap,a)
        #     self.pieces[piece_index][self.num_blocks_last-1]=a
        #     return (a.offset,a.size)
        return (None,None)

    def find_next_block(self, piece_index):
        flag = False
        i = 0
        # if(len(self.block_heap) and has_expired and self.block_heap[0].piece==piece_index):
        #     print("picking expired block")
        #     self.block_heap[0].began_requesting=time.time()
        #     a=self.block_heap[0]
        #     heapq.heapify(self.block_heap)
        #     return (a.offset,a.size)
        if (piece_index==self.no_pieces-1):
            # print("picking block of last piece")    
            # generate_heading("Looking at the last piece")
            return self.get_last_piece(piece_index)

        for i in range(self.num_blocks):
            # print("picking a block")

            if (i not in self.pieces[piece_index]):
                flag = True
                # a=Block(piece_index,2**14*i,2**14)
                # heapq.heappush(self.block_heap,a)
                # self.pieces[piece_index][i]=a
                return (2**14*i,2**14)
        if (not(flag)):
            # print("don't be here, fool!!!!!!!!!")
            return (None,None)
    
    # def try_handshake(self,client,peer_index):
    #     generate_heading(f"Handshaking with ({self.peers[peer_index].ip}, {self.peers[peer_index].port})...")
    #     a=self.peers[peer_index].send_handshake(client)
    #     if(a["status"]==0):
    #         return 0
    #     generate_heading(f"Sending interested to ({self.peers[peer_index].ip}, {self.peers[peer_index].port})...")
    #     b=self.peers[peer_index].send_interested(client)
    #     if(b["status"]==0):
    #         # print("ergrg")
    #         return 0
    #     return 1

    async def start_messaging(self):

        await asyncio.gather(*([peer.connect() for peer in self.peers]))
        self.create_piece_dict()
        #fill 4 pieces at random first
        # generate_heading(f"No. of Peers: {len(self.peers)}")
        self.peers=[peer for peer in self.peers if peer.writer!=None and peer.reader!=None]
        # print(len(self.peers))
        asyncio.create_task(self.top_four())
        await asyncio.gather(*([peer.begin() for peer in self.peers]))

    def get_rarest_piece(self):
        piece_available_freq=np.array([0]*self.no_pieces)
        for peer in self.peers:
            if(peer.peer_choking==0):
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
        # print("Piece Status: ")
        # print(np.where(np.array(self.piece_status)==1)[0])
        if (sum(self.piece_status)==self.no_pieces):
            generate_heading("All done")
            return (None, True,False)
        #check if any block has timedout
        if(len(self.block_heap) and self.block_heap[0].began_requesting+20<time.time()):
            # generate_heading(f"Re-Requesting {self.block_heap[0].piece} | {self.block_heap[0].offset} | heap_size: {len(self.block_heap)}")
            return (self.block_heap[0].piece,False,True)
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
                return (self.downloading_piece, False,False)
            else:
                return (self.downloading_piece, False,False)
        elif(self.state==1):
            #rarest first
            # print("Downloading:",self.downloading_piece)
            # generate_heading("In rarest first")
            if(self.downloading_piece== None):
                piece_index=self.get_rarest_piece()
                # generate_heading(f"Piece index: {piece_index}")
                self.downloading_piece=piece_index
                return (self.downloading_piece, False,False)
            else:
                return (self.downloading_piece, False,False)
    
    def complete(self):
        data = b""
        # generate_heading("Here")
        # for piece in self.pieces:
        #     # print(piece)
        #     generate_heading(f"Piece index: {piece}")
        #     data = b""
        #     for block in self.pieces[piece].values():
        #         data += block.data
        #     print(data)
        #     print()
        print()

    def http_request(self,url,params):
        params["compact"] = 1
        announce_response = requests.get(url,params).content
        response_dict = bencodepy.decode(announce_response)
        if(type(response_dict[b'peers'])==list):
            for x in response_dict[b'peers']:
                if((x[b'ip'].decode(),x[b'port']) not in piport):
                    # self.peers.append(Peer(self.peer_id,self.info_hash,x[b'ip'].decode(),x[b'port'],self.no_pieces,self.find_next_block,self.write_block,self.get_piece_index,self.rerequest_piece,self.complete))
                    piport.append((x[b'ip'].decode(),x[b'port']))
                    self.peer_dict[(x[b'ip'].decode(),x[b'port'])] = True
                    # print(x[b'ip'].decode(),x[b'port'])
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
                    # self.peers.append(Peer(self.peer_id,self.info_hash,ip,port,self.no_pieces,self.find_next_block,self.write_block,self.get_piece_index,self.rerequest_piece,self.complete))
                    self.peer_dict[(ip,port)] = True
                    # print(ip,port)
                    piport.append((ip,port))
    
    def udp_request(self,url,params):
        def connection_upload_udp(connection_id, action, transaction_id):
            payload = struct.pack("!q", connection_id)
            payload += struct.pack("!i", action)
            payload += struct.pack("!i", transaction_id)
            return payload
        
        def parse_udp_tracker_url(tracker_url):
            domain_url = tracker_url[6:].split(':')
            udp_tracker_url = domain_url[0]
            udp_tracker_port = int(domain_url[1].split('/')[0])
            return (udp_tracker_url, udp_tracker_port)
        
        # connect
        connection_id = 0x41727101980
        action = 0x0
        transaction_id = int(random.randrange(0, 255))
        # tracker_url = url.decode("unicode_escape")
        # print(parse_udp_tracker_url(tracker_url))
        url, port = parse_udp_tracker_url(url)

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
        try:
            raw_conn_data, conn = tracker_sock.recvfrom(2048)
        except Exception as e:
            return
        if (len(raw_conn_data) < 16):
            raise NotImplementedError()
        else:
            # action
            action = struct.unpack_from("!i", raw_conn_data, 0)[0]
            exp = action==0x0
            if (action!=0x0):
                print("Error: action didn't match expected value in 0")
            # transaction_id
            tid = struct.unpack_from("!i", raw_conn_data, 4)[0]
            if (tid!=transaction_id):
                print("Error: transaction ids did not match")
            # connection_id
            cid = struct.unpack_from("!q", raw_conn_data, 8)[0]

            # print(action, tid, cid)

        """
            Choose a random transaction ID.
            Fill the announce request structure.
            Send the packet.
        """
        # POTENTIAL PROBLEM
        transaction_id = random.randrange(0,255)

        def create_announce_payload(cid, action, transaction_id):
            action = 0x1
            event = 0x2
            IP = 0x0
            payload = struct.pack("!q", cid)
            payload += struct.pack("!i", action)
            payload += struct.pack("!i", transaction_id)
            payload += struct.pack("!20s", params['info_hash'])
            payload += struct.pack("!20s", params['peer_id'])
            payload += struct.pack("!q", params['downloaded'])
            payload += struct.pack("!q", params["left"])
            payload += struct.pack("!q", params['uploaded'])
            payload += struct.pack("!i", event)
            payload += struct.pack("!i", IP)
            payload += struct.pack("!i", random.randint(0,255))
            payload += struct.pack("!i", -1)
            payload += struct.pack("!h", port)
            return payload

        announce_payload = create_announce_payload(cid, action, transaction_id)
        # print(announce_payload)
        tracker_sock.sendto(announce_payload, (url, port))

        """
            Receive the packet.
            Check whether the packet is at least 20 bytes.
            Check whether the transaction ID is equal to the one you chose.
            Check whether the action is announce.
            Do not announce again until interval seconds have passed or an event has occurred.
        """

        attempt = 0
        raw_announce_data,conn = tracker_sock.recvfrom(65535)
        peers_list = []
        if (len(raw_announce_data)<20):
            return
        else:
            # action
            action = struct.unpack_from("!i", raw_announce_data, 0)[0]
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
            offset=20
            while(offset != len(raw_announce_data)):
                # first 4 bytes is the peer IP address
                raw_peer_IP = struct.unpack_from("!4s", raw_announce_data, offset)[0]
                peer_IP = ".".join(str(a) for a in raw_peer_IP)
                # next 2 bytes is the peer port address
                peer_port = int(struct.unpack_from("!H", raw_announce_data, offset + 4)[0])
                # print(peer_IP, peer_port)
                self.peer_dict[peer_IP, peer_port] = True
                offset = offset + 6

            # print(interval, leechers, seeders)
            # print("Done parsing UDP")
        
    def is_http(self,url):
        if ('http' in url):
            return True
        else:
            return False

    def get_peers(self):
        self.peers=[]
        self.peer_dict = {}
        if(self.peer_id==''):
            self.peer_id='VS2083'+str(random.randint(10000000000000, 99999999999999))
        i=0
        params={
            "info_hash":self.info_hash,
            "peer_id":self.peer_id.encode(),
            "port":self.port,
            "uploaded":self.uploaded,
            "downloaded":self.downloaded,
            "left":self.left,
            'event': 'started',
        }
        self.tracker_urls=list(set(self.tracker_urls))
        responses=[]
        loop=0
        while(len(responses)==0 and loop<1):
            # print(f"Looping {loop+1} time")
            i=0
            while i<len(self.tracker_urls):
                url=self.tracker_urls[i]
                try:
                    if self.is_http(url):
                        generate_heading("HTTP")
                        print(url)
                        self.http_request(url,params)
                    else:
                        generate_heading("UDP")
                        print(url)
                        # self.udp_request(url,params)
                except Exception as e:
                    print(e)
                i+=1
            loop+=1
        
        for peer in self.peer_dict:
            # print(peer)
            self.download_rates[(peer[0], peer[1])] = 0
            self.peers.append(Peer(self.peer_id,self.info_hash,peer[0],peer[1],self.no_pieces,self.find_next_block,self.write_block,self.get_piece_index,self.rerequest_piece,self.complete,self.get_piece_block,self.allDownloaded,self.update_rate,self.create_message))
    
    def create_message(self):
        bitstring = "".join(self.piece_status)
        bitstring = bitstring.encode()
        return 1+len(self.piece_status),bitstring
    
    async def top_four(self):
        while True:
            if (sum(self.piece_status)==self.no_pieces):
                # generate_heading("Completed. Exiting top four...")
                sys.exit(0)
            # if (self.state==1):
            if (sum(self.piece_status)>4):
                # generate_heading("Finding top 4 peers...")
                for peer in self.unchoked_peers:
                    # print(peer.ip, peer.port)
                    await peer.send_choke()
                self.unchoked_peers = nlargest(4,self.peers,key=lambda peer: peer.download_rate)
                for peer in self.unchoked_peers:
                    # print(peer.ip, peer.port)
                    await peer.send_unchoke()
            await asyncio.sleep(5)
    
    def update_rate(self,rate,ip,port):
        generate_heading(f"Rate of {ip} {port} updated from {self.download_rates[(ip, port)]} to {rate}")
        self.download_rates[(ip,port)] = rate
        generate_heading("Upload rate")
        for addr,rate in self.download_rates.items():
            print(addr[0],addr[1],rate)
