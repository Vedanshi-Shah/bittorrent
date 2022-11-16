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
ENDGAME = 7

class Tracker:
    def __init__(self,filename):
        self.filename='../torrent_files/'+filename
        with open(self.filename, "rb") as f:
            self.raw_data = bencodepy.decode(f.read())
            self.file_name = self.raw_data[b'info'][b'name'].decode()
            self.tracker_urls=[]
            if('announce-list'.encode() in self.raw_data.keys()):
                for u in self.raw_data['announce-list'.encode()]:
                    self.tracker_urls.append(u[0].decode())
            if('announce'.encode() in self.raw_data.keys()):
                self.tracker_urls.append(self.raw_data['announce'.encode()].decode())
            if(b'files' in self.raw_data[b'info']):
                self.mode=1
            else:
                self.mode=0
            self.file_length=0
            self.multi_files=[]
            if(self.mode==1):
                #multifile
                self.file_type_text = "Multiple files"
                self.cumulative_len=[]
                files=self.raw_data[b'info'][b'files']
#                print(files)
                for f in files:
                    self.file_length+=f[b'length']
                    directory_name=""
                    for a in f[b'path']:
                        directory_name+=a.decode()+"/"
                    directory_name=directory_name[:len(directory_name)-1]
                    self.multi_files.append((directory_name,f[b'length']))
                    self.cumulative_len.append(self.file_length)
            else:
                self.file_length=self.raw_data['info'.encode()]['length'.encode()]
            self.fileordir_name=self.raw_data['info'.encode()]['name'.encode()].decode()
            # print(self.raw_data[b'info'][b'length'])
            self.piece_length=self.raw_data['info'.encode()]['piece length'.encode()]
            
            self.pieces_info=self.raw_data['info'.encode()]['pieces'.encode()]
            info_bencoded=bencodepy.encode(self.raw_data['info'.encode()])
            self.info_hash=hashlib.sha1(info_bencoded).digest()
            self.peer_id=''
            self.port=6884
            self.uploaded=0
            self.downloaded=0
            self.left=self.file_length-self.downloaded
#            print(self.file_length, self.piece_length, self.file_length/self.piece_length)
            self.no_pieces=math.ceil(self.file_length/self.piece_length)
            self.piece_status=[0]*self.no_pieces
            self.pieces = {}
            self.num_blocks = math.ceil(self.piece_length/BLOCK_LENGTH)
#            generate_heading(f"Total file length: {self.file_length}")
#            generate_heading(f"Piece length: {self.piece_length}")
#            generate_heading(f"Num blocks: {self.num_blocks}")
            self.create_piece_dict()
            self.downloading_piece = None
            self.state=0 #0 for random first, 1 for rarest first & 2 for endgame
#            generate_heading(f"No. of Pieces: {self.no_pieces}")
            self.last_piece_length = self.file_length-(self.no_pieces-1)*self.piece_length
            self.num_blocks_last = math.ceil(self.last_piece_length/2**14)
            self.block_heap=[]
            self.get_pieces_hashes()
#            print("Last piece length:",self.last_piece_length)
#            print("Blocks in last piece:",self.num_blocks_last)
            # self.print_hashes()
            self.create_file()
            self.unchoked_peers = []
            self.download_rates = {}
            self.upload_rates = {}
            self.num_downloaded_blocks=0
            self.piece_queue=[]
            self.to_be_downloaded={}
            self.inEndgame=0
#             if(self.mode==1):
# #                print(self.multi_files)
            self.file_length_text = self.human_file_length()
            self.downloaded = 0
    def human_file_length(self):
        how_many = 0
        while (self.file_length>1000):
            self.file_length = self.file_length/1024
            how_many += 1
        self.how_many = how_many
        if (how_many==0):
            self.name_size = "B"
            return f"{self.file_length: .2f} B"
        if (how_many==1):
            self.name_size = "kB"
            return f"{self.file_length: .2f} kB"
        if (how_many==2):
            self.name_size = "MB"
            return f"{self.file_length: .2f} MB"
        if (how_many==3):
            self.name_size = "GB"
            return f"{self.file_length: .2f} GB"

    def Display(self):
        os.system('clear')
        if (self.mode==0):
            mode = "Single file"
        else:
            mode = "Multiple files"
        generate_heading(f"Filename: {self.file_name} | {mode}")
        generate_heading(f"File length: {self.file_length_text}")
        generate_heading(f"Number of peers connected: {len(self.peers)}")
        generate_heading(f"Num pieces: {self.no_pieces} | Num blocks per piece: {self.num_blocks} | Num downloaded blocks: {self.num_downloaded_blocks} | Last piece length: {self.last_piece_length} | Num last blocks: {self.num_blocks_last}")
        self.download_progress()

    
    def create_file(self):
        if(self.mode==1):
            #multi files
            if not os.path.exists(self.fileordir_name):
                os.mkdir(self.fileordir_name)
            for fn in self.multi_files:
#                print(fn[0])
                direct=self.fileordir_name+"/"+'/'.join(fn[0].split('/')[:-1])+"/"
#                print(direct)
                if not os.path.exists(direct):
                    os.mkdir(direct)
                with open(self.fileordir_name+"/"+fn[0],"w") as f:
                    pass
                f.close()
        else:
            #single file
            with open(self.fileordir_name,"w") as f:
                pass
        with open("logs.txt", "w") as f:
            pass
    
    def sayEndgame(self):
        if(self.inEndgame):
            return True
        else:
            return False

    def average_rate(self):
        rates = np.fromiter(self.download_rates.values(), dtype=float)
        nums = np.sum(rates!=0)
        return np.sum(rates)/nums

    def allDownloaded(self):
        # print(self.piece_status)
        if(sum(self.piece_status)==self.no_pieces):
            # self.top_four_task.cancel()
            return True
        return False
    
    async def end_game_mode(self,ip,port):
        exp_blocks=[b for b in self.block_heap if b.began_requesting+10<time.time()]
        if(len(exp_blocks)>0):
            i=np.random.randint(0,len(exp_blocks))
            exp_blocks[i].began_requesting=time.time()
            heapq.heapify(self.block_heap)
            for p in self.peers:
                p.downloading=1
                if(p.writer!=None):
                    await p.send_request_message(exp_blocks[i].piece,exp_blocks[i].offset,exp_blocks[i].size)
        else:
            bo,bl=self.find_next_block(self.piece_queue[0],ip,port)
            # generate_heading(f"Found {bo} {bl}")
            if (bo!=None):
                a=Block(self.piece_queue[0],bo,bl)
                heapq.heappush(self.block_heap,a)
                heapq.heapify(self.block_heap)
                self.pieces[self.piece_queue[0]][math.ceil(bo/2**14)]=a
                for p in self.peers:
                    # if(p.downloading==0):
                    p.downloading=1
                    if(p.writer!=None):
                        await p.send_request_message(self.piece_queue[0],bo,bl)
    
    async def send_block(self,piece_index,block_offset,block_length,writer):
        # generate_heading(f"Sending {piece_index} {block_offset} {block_length}")
        if (self.piece_status[piece_index]==1):
            if self.mode==1:
                writer.write(self.pieces[piece_index][block_offset])
                await writer.drain()
            else:
                # Open the file
                pos = piece_index * self.piece_length
                async with aiofiles.open(self.filename, "rb+") as f:
                    await f.seek(pos,0)
                    data = await f.read(block_length)
                    writer.write(data)
                    await writer.drain()

    async def get_piece_block(self,ip,port):
        # check if all pieces have been receive
        if(sum(self.piece_status)>=self.no_pieces):
            # self.top_four_task.cancel()
            return (None,None,None,True)
        if(self.no_pieces>=ENDGAME and self.num_blocks*(self.no_pieces-1)+self.num_blocks_last-self.num_downloaded_blocks<ENDGAME):
            #call endgame function
            #once done return N,N,N,T
            self.state = 2
            self.inEndgame=1
            # generate_heading("In Endgame Mode")
            await self.end_game_mode(ip,port)
            return (None,None,None,False)
        else:
            exp_blocks=[b for b in self.block_heap if b.began_requesting+10<time.time()]
        
            if(len(exp_blocks)>0):#check if any block has expired
                # generate_heading("Picking an expired block")
                i=np.random.randint(0,len(exp_blocks))
                exp_blocks[i].began_requesting=time.time()
                heapq.heapify(self.block_heap)
                return (exp_blocks[i].piece,exp_blocks[i].offset,exp_blocks[i].size,False)
            else:
                # Random first or rarest first
                # generate_heading(f"Piece and block number being requested by {ip} | {port}")
                # generate_heading(f"Queue size: {len(self.piece_queue)}")
                i=0
                while(i<min(5,len(self.piece_queue))):
                    self.downloading_piece=self.piece_queue[i]
                    block_offset,block_size=self.find_next_block(self.downloading_piece,ip,port)
                    if(block_offset!=None):
                        a=Block(self.downloading_piece,block_offset,block_size)
                        heapq.heappush(self.block_heap,a)
                        heapq.heapify(self.block_heap)
                        self.pieces[self.downloading_piece][math.ceil(block_offset/2**14)]=a
                        return (self.downloading_piece,block_offset,block_size,False)
                    i+=1
                        

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
        self.to_be_downloaded=list(self.pieces.keys())
    def rerequest_piece(self):
        exp_blocks=[b for b in self.block_heap if b.began_requesting+20<time.time()]
        if(len(exp_blocks)>0):
            i=np.random.randint(0,len(exp_blocks))
            self.block_heap[i].began_requesting=time.time()
            heapq.heapify(self.block_heap)
            return (self.block_heap[i].piece,self.block_heap[i].offset,self.block_heap[i].size,False)
        else:
            # print("meow")
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
            # self.pieces[piece_index] = {}
            # self.piece_status[piece_index] = 0
            # generate_heading("Corrupted piece")
            return False,None
        return True,data
    
    async def write_piece(self,piece_index,data):
        # generate_heading("Piece verified and being written")
        def search(ele):
            low=0
            high=len(self.cumulative_len)-1
            
            while(low<=high):
                mid=(high+low)//2
                if(self.cumulative_len[mid]==ele):
                    return mid
                elif(self.cumulative_len[mid]>ele):
                    high=mid-1
                else:
                    low=mid+1

            return low
        
        if(self.mode==1):
            start_pos=piece_index*self.piece_length
            end_pos=(piece_index+1)*self.piece_length
            si=search(start_pos)
            ei=search(end_pos)
            ei=min(ei,len(self.cumulative_len))
            data_offset = 0
            last_length = start_pos
            # generate_heading(f"Piece Index: {piece_index} :-> {(si,ei)}")
            f1=open("logs.txt","a")
            if(si!=0):
                start_pos=start_pos-self.cumulative_len[si-1]
            for i in range(si,ei+1):
                end=min(self.cumulative_len[i],end_pos)
                async with aiofiles.open(self.fileordir_name+"/"+self.multi_files[i][0],"rb+") as f:
                    await f.seek(start_pos,0)
                    await f.write(data[data_offset:data_offset+(end-last_length)])
                    f1.write(f"{i} :- {(piece_index,end-last_length)}\n")
                data_offset += end-last_length
                last_length = self.cumulative_len[i]
                start_pos=0

        else:
            async with aiofiles.open(self.fileordir_name, "rb+") as f:
                pos = piece_index * self.piece_length
                await f.seek(pos, 0)
                await f.write(data)
        # f.close()
    
    def broadcast_have(self, piece_index):
        # generate_heading("Broadcasting have...")
        for peer in self.peers:
            if(peer.writer!=None):
                peer.send_have(piece_index)

    async def log(self, piece_index, block_num, block_length, ip, port):
        async with aiofiles.open("logs.txt", "a") as f:
            await f.write(f"{piece_index} | {block_num} | {block_length} => {ip}:{port}\n")
    
    async def write_block(self,piece_index,block_offset,block_data,ip,port):
        # print(piece_index,block_offset,ip,port)
        # if(self.pieces[piece_index][math.ceil(block_offset/2**14)].status==2):
        #     return
        # generate_heading(f"{piece_index} | {block_offset} |")
        # self.pieces[piece_index][math.ceil(block_offset/2**14)]=Block(piece_index,math.ceil(block_offset/2**14),len(block_data))
        if (self.piece_status[piece_index]==1):
            # print("308: returned")
            return
        # If all blocks have been received - the piece is yet to be verified
        if(self.pieces[piece_index][math.ceil(block_offset/2**14)].data==b''):
            # print("312")
            self.num_downloaded_blocks+=1
        else:
            return
        self.pieces[piece_index][math.ceil(block_offset/2**14)].data=block_data
        self.pieces[piece_index][math.ceil(block_offset/2**14)].status=2
        # print("316")
        
        self.download_progress()
        # try:
        #     await self.download_progress()
        # except Exception as e:
        #     print("error while printing download progress:",e)
        if(self.inEndgame):
            for p in self.peers:
                if(p.ip!=ip or p.port!=port):
                    if(p.writer!=None):
                        p.send_cancel(piece_index,block_offset,len(block_data))   
        # print("328")
        if(sum(self.piece_status)==4):
            # generate_heading(f"Entered rarest first")
            self.state=1
        # print("332")
        flag=False
        if (self.is_piece_complete(piece_index)):
            # print("335")
            is_verified,data = self.verify_piece(piece_index)
            # print("337")
            # print("353:",self.pieces[piece_index])
            if (is_verified):
                # Need to await here
                # generate_heading(f"Verified piece {piece_index}")
                self.downloading_piece=None
                self.piece_status[piece_index]=1
                # print(f"Before Popping:",self.piece_queue)
                # print("344")
                self.piece_queue.remove(piece_index)
                # print("346")
                # print(f"Piece No. Popped {piece_index}",self.piece_queue)
                # generate_heading(f"Length of t be downloaded: {len(self.to_be_downloaded)}")
                if(len(self.to_be_downloaded)!=0):
                    # generate_heading("What are you looking at?")
                    # Random first
                    if (self.state==0):
                        k=np.random.randint(len(self.to_be_downloaded))
                        k=self.to_be_downloaded[k]
                        # print("353")
                    # Rarest first
                    else:
                        
                        k = self.get_rarest_piece()
                        
                    # print("359")
                    # generate_heading(f"Adding piece {k} to the queue")
                    self.piece_queue.append(k)
                    # print("364")
                    self.to_be_downloaded.remove(k)
                    # print("366")
                await self.write_piece(piece_index,data)
                # self.broadcast_have(piece_index)
            else:
                generate_heading(f"Corrupted Piece {piece_index}")
                flag=True
                self.downloading_piece=None
                self.num_downloaded_blocks-=len(self.pieces[piece_index])
                print("389:",math.ceil(block_offset/2**14))
                print("390:",self.pieces[piece_index])
                # for p in self.pieces[piece_index].values():
                #     self.block_heap.remove(p)
                # if(sum(self.piece_status)<self.no_pieces):
                #     flag=True
                #     while flag:
                #         k=np.random.randint(0,self.no_pieces)
                #         if(self.piece_status[k] or k in self.piece_queue):
                #             continue
                #         else:
                #             flag=False
                #             self.piece_queue.append(k)
                # del self.pieces[piece_index]
                # generate_heading(f"Number of pieces downloaded: {sum(self.piece_status)}")

        # print("138: meow",len(self.block_heap))
        self.downloaded += len(block_data)
        # print("404")
        self.block_heap.remove(self.pieces[piece_index][math.ceil(block_offset/2**14)])
        # print("406")
        # print("139: meow",len(self.block_heap))
        heapq.heapify(self.block_heap)
        if(flag==True):
            self.pieces[piece_index] = {}
        self.Display()
        await self.log(piece_index, math.ceil(block_offset/2**14), len(block_data), ip, port)

    def download_progress(self):
        # From which peer was the block received
        percent=(self.num_downloaded_blocks/((self.no_pieces-1)*self.num_blocks+self.num_blocks_last))*100
        # print(percent)
        arr=["#"]*math.ceil(percent)+[" "]*(100-math.ceil(percent))
        progress = ''.join(arr)
        print()
        print("Progress")
        generate_heading(f'{progress}')
        print()
        print(f"Average Download Rate: {self.average_rate()/1024: .2f} kBps")
        print(f"Downloaded: {self.downloaded/(1024**self.how_many): .2f} {self.name_size} | Total: {self.file_length_text}")
    
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

    def find_next_block(self, piece_index,ip,port):
        flag = False
        i = 0
        # if(len(self.block_heap) and has_expired and self.block_heap[0].piece==piece_index):
        #     print("picking expired block")
        #     self.block_heap[0].began_requesting=time.time()
        #     a=self.block_heap[0]
        #     heapq.heapify(self.block_heap)
        #     return (a.offset,a.size)
        # print(self.pieces[piece_index])
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
            # print(f"don't be here, fool!!!!!!!!! {piece_index} | {ip} | {port}")
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
        self.piece_queue = list(np.random.choice(self.no_pieces,size=min(5,self.no_pieces),replace=False))
        self.to_be_downloaded = list(set(self.to_be_downloaded)-set(self.piece_queue))
        self.top_four_task=asyncio.create_task(self.top_four())
        await asyncio.gather(*([peer.begin(math.ceil((self.no_pieces-1)*self.num_blocks+self.num_blocks_last)/len(self.peers)) for peer in self.peers]))
        # await asyncio.gather(*([peer.pure_seeding() for peer in self.peers if peer.reader!=None and peer.writer!=None]))

    def get_rarest_piece(self):
        piece_available_freq=np.array([0]*self.no_pieces)
        for peer in self.peers:
            if(peer.peer_choking==0):
                piece_available_freq += peer.present_bits
        min_elems = np.argsort(piece_available_freq)
        # print(min_elems[:3])
        for elem in min_elems:
            if (self.piece_status[elem] or elem not in self.to_be_downloaded):
                continue
            else:
                return elem
        # print("I shouldn't have been here")
        
    def get_piece_index(self):
        # print("Piece Status: ")
        # print(np.where(np.array(self.piece_status)==1)[0])
        if (sum(self.piece_status)>=self.no_pieces):
            # generate_heading("All done")
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
        # generate_heading("Complete called...")
        # self.top_four_task.cancel()
        # self.top_four_task = asyncio.create_task()
        # generate_heading("Here")
        # for piece in self.pieces:
        #     # print(piece)
        #     generate_heading(f"Piece index: {piece}")
        #     data = b""
        #     for block in self.pieces[piece].values():
        #         data += block.data
        #     print(data)
        #     print()
        # print()
        # sys.exit(0)
    
    async def update_peers(self):
        while True:
            self.peers=[p for p in self.peers if p.writer!=None and p.reader!=None]
            generate_heading("Updating trackers...")
            await asyncio.sleep(30)
    
    async def rerequest_trackers(self):
        while True:
            if(self.lastCallTracker+self.maxInterval<time.time()):
                generate_heading("Rerequesting trackers...")
                self.get_peers()
            await asyncio.sleep(30)

    def http_request(self,url,params):
        params["compact"] = 1
        # print(params)
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

    # def http_request(self,url,params):
    #     params["compact"] = 1
    #     announce_response = requests.get(url,params).content
    #     response_dict = bencodepy.decode(announce_response)
    #     self.maxInterval=max(self.maxInterval,response_dict[b'interval'])
    #     if(type(response_dict[b'peers'])==list):
    #         for x in response_dict[b'peers']:
    #             if((x[b'ip'].decode(),x[b'port']) not in piport):
    #                 # self.peers.append(Peer(self.peer_id,self.info_hash,x[b'ip'].decode(),x[b'port'],self.no_pieces,self.find_next_block,self.write_block,self.get_piece_index,self.rerequest_piece,self.complete))
    #                 piport.append((x[b'ip'].decode(),x[b'port']))
    #                 self.peer_dict[(x[b'ip'].decode(),x[b'port'])] = True
    #     else:
    #         p=response_dict[b'peers']
    #         offset=0
    #         while offset<len(p):
    #             ip_number = struct.unpack_from("!I", p, offset)[0]
    #             ip = inet_ntoa(struct.pack("!I", ip_number))
    #             offset += 4
    #             port = struct.unpack_from("!H", p, offset)[0]
    #             offset += 2
    #             if((ip,port) not in piport):
    #                 # self.peers.append(Peer(self.peer_id,self.info_hash,ip,port,self.no_pieces,self.find_next_block,self.write_block,self.get_piece_index,self.rerequest_piece,self.complete))
    #                 self.peer_dict[(ip,port)] = True
    #                 piport.append((ip,port))
    
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
            print(e)
            # return
        if (len(raw_conn_data) < 16):
            raise NotImplementedError()
        else:
            # action
            action = struct.unpack_from("!i", raw_conn_data, 0)[0]
            exp = action==0x0
            if (action!=0x0):
                print("error connecting")
                # return
            # transaction_id
            tid = struct.unpack_from("!i", raw_conn_data, 4)[0]
            if (tid!=transaction_id):
                print("error connecting")
                # return
            # connection_id
            cid = struct.unpack_from("!q", raw_conn_data, 8)[0]


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
                print("error connecting")
                # return
            # transaction_id
            tid = struct.unpack_from("!i", raw_announce_data, 4)[0]
            if (tid!=transaction_id):
                print("error connecting")
                # return
            # interval
            interval = struct.unpack_from("!i", raw_announce_data, 8)[0]
            leechers = struct.unpack_from("!i", raw_announce_data, 12)[0]
            seeders = struct.unpack_from("!i", raw_announce_data, 16)[0]
            self.maxInterval=max(self.maxInterval,interval)
            offset=20
            while(offset != len(raw_announce_data)):
                # first 4 bytes is the peer IP address
                raw_peer_IP = struct.unpack_from("!4s", raw_announce_data, offset)[0]
                peer_IP = ".".join(str(a) for a in raw_peer_IP)
                # next 2 bytes is the peer port address
                peer_port = int(struct.unpack_from("!H", raw_announce_data, offset + 4)[0])
                self.peer_dict[peer_IP, peer_port] = True
                offset = offset + 6
    
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
        generate_heading(f" Connecting to trackers... ")
        self.peer_id = self.peer_id.encode()
        params={
            "info_hash":self.info_hash,
            "peer_id":self.peer_id,
            "port":self.port,
            "uploaded":self.uploaded,
            "downloaded":self.downloaded,
            "left":self.left,
            'event': 'started',
        }
        self.tracker_urls=list(set(self.tracker_urls))
        responses=[]
        http_trackers = 0
        udp_trackers = 0
        loop=0
        while(len(responses)==0 and loop<1):
            i=0
            while i<len(self.tracker_urls):
                url=self.tracker_urls[i]
                try:
                    if self.is_http(url):
                        http_trackers += 1
                        self.http_request(url,params)
                    else:
                        udp_trackers += 1
                        self.udp_request(url,params)
                except Exception as e:
                    print("error")
                i+=1
            loop+=1
        self.lastCallTracker = time.time()
        self.http_trackers = http_trackers
        self.udp_trackers = udp_trackers
        print(f"Contacted {http_trackers} HTTP trackers")
        print(f"Contacted {udp_trackers} UDP trackers")
        for peer in self.peer_dict:
            self.download_rates[(peer[0], peer[1])] = 0
            self.peers.append(Peer(self.peer_id,self.info_hash,peer[0],peer[1],self.no_pieces,self.find_next_block,self.write_block,self.get_piece_index,self.rerequest_piece,self.complete,self.get_piece_block,self.allDownloaded,self.update_rate,self.create_message,self.sayEndgame,self.send_block))
    
    def create_message(self):
        bitstring = "".join([str(x) for x in self.piece_status])
        bitstring = bitstring.encode()
        len_bitstring = len(bitstring)
        return 1+len_bitstring,bitstring
    
    async def top_four(self):
        while True:
            # if (self.state==1):
            if (sum(self.piece_status)>4):
                temp = nlargest(4,self.peers,key=lambda peer: peer.download_rate)
                for peer in self.peers:
                    if (peer.am_choking!=1 and peer not in temp and peer.writer!=None):
                        peer.send_choke()
                self.unchoked_peers = temp
                for peer in self.unchoked_peers:
                    if(peer.writer!=None):
                        peer.send_unchoke()
            await asyncio.sleep(5)
    
    def update_rate(self,rate,ip,port):
        # generate_heading(f"Rate of {ip} {port} updated from {self.download_rates[(ip, port)]} to {rate}")
        self.download_rates[(ip,port)] = rate
        # generate_heading("Upload rate")
        # for addr,rate in self.download_rates.items():
        #     print(addr[0],addr[1],rate)