from socket import *
import struct
import bitstring
import sys
import random
from prettify import generate_heading, keys_values
import asyncio
import numpy as np
import time
import os

class Peer:
    def __init__(self,peer_id,info_hash,ip,port,no_pieces,find_next_block,write_block,get_piece_index,rerequest_piece,complete,get_piece_block,allDownloaded,update_rate,create_message):
        self.ip=ip
        self.port=port
        self.am_choking=1
        self.am_interested=0
        self.peer_choking=1
        self.peer_interested=0
        self.info_hash=info_hash
        self.downloading = 0
        self.id=peer_id
        self.remote_id=''
        self.present_bits=np.array([0]*no_pieces)
        self.no_pieces = no_pieces
        self.find_next_block = find_next_block
        self.write_block = write_block
        self.get_piece_index = get_piece_index
        self.in_download_block = None
        self.in_download_piece = None
        self.in_download_length = None
        self.reader=None
        self.writer=None
        self.rerequest_piece=rerequest_piece
        self.complete = complete
        self.last_requested=0
        self.get_piece_block=get_piece_block
        self.allDownloaded=allDownloaded
        self.download_rate = 0
        self.update_rate = update_rate
        self.num_downloaded_blocks = 0
        self.download_start = 0
        self.create_message = create_message
    
    def average_rate(self,curr_rate,new_rate):
        return (curr_rate*(self.num_downloaded_blocks-1)+new_rate)/(self.num_downloaded_blocks)

    def get_download_rate(self,block_length):
        # print(block_length)
        rate = block_length/(time.time()-self.download_start)
        # print(rate)
        self.download_rate = self.average_rate(self.download_rate,rate)
        # print(self.download_rate)
        return self.download_rate
    
    async def send_interested(self):
        # try:
        interested_msg=struct.pack("!Ib",1,2)
        self.writer.write(interested_msg)
        await self.writer.drain()
        # except Exception as e:
        #     print("Here")
        #     print(e)
        #     return {"status":0}

    async def send_handshake(self):
        # generate_heading(f"Sending Handshake to {self.ip} | {self.port}")
        handshake_msg=struct.pack("!b19sq20s20s",19,"BitTorrent protocol".encode(),0,self.info_hash,self.id.encode())
        self.writer.write(handshake_msg)
        await self.writer.drain()
        s=b''
        # Can receive a BitField after handshake
        # while len(s)<68:
        s+=await asyncio.wait_for(self.reader.read(65535),10)
        decoded_recv_data = struct.unpack("!b19sq20s20s", s[:68])
        if decoded_recv_data[3] != self.info_hash:
            raise Exception("Invalid Peer Connection")
        s=b''
        offset=0
        try:
            s+=await asyncio.wait_for(self.reader.read(65535),2)
            # print(s)
            if(len(s)>4):
                msg_len=struct.unpack_from("!i",s)[0]
                offset+=4
                msg_id=struct.unpack_from("!B",s,offset)[0]
                offset+=1
                if(msg_id==5):
                    bitfield=s[offset:]
                    bitfield=bitstring.BitArray(bitfield).bin
                    self.set_bitfield(bitfield)
        except Exception as e:
            print("Handshake ke baad bitfield nahi aya",e)

    async def connect(self):
        try:
            # print(self.ip, self.port)
            self.reader,self.writer = await asyncio.wait_for(asyncio.open_connection(self.ip,self.port),4)
            
        except Exception as e:
            self.reader=None
            self.writer=None
            print(e)

    def send_request_message(self,piece_index,block_offset,block_length):
        # Index, Block Offset, Block length
        # print(piece_index, block_offset, block_length)
        req_message=struct.pack("!IB",13,6)
        payload = struct.pack("!i", piece_index)
        payload += struct.pack("!i", block_offset)
        payload += struct.pack("!i", block_length)
        req_message += payload
        # print(f"Requesting (piece_index = {piece_index}, block_offset = {block_offset}, block_length = {block_length})...")
        self.last_requested=time.time()
        self.writer.write(req_message)
        # self.writer.drain()
    
    async def send_keep_alive(self):
        generate_heading("Sending Keep Alive")
        keep_alive_message = struct.pack("!I",0)
        self.writer.write(keep_alive_message)
        await self.writer.drain()
    
    async def send_choke(self):
        generate_heading("Sending choke")
        choke_message = struct.pack("!IB",1,0)
        self.writer.write(choke_message)
        await self.writer.drain()
    
    async def send_unchoke(self):
        generate_heading("Sending unchoke")
        unchoke_message = struct.pack("!IB",1,1)
        self.writer.write(unchoke_message)
        await self.writer.drain()
    
    async def send_have(self,piece_index):
        generate_heading("Sending have")
        have_message = struct.pack("!IB",5,4)
        have_message += struct.pack("!I",piece_index)
        self.writer.write(have_message)
        await self.writer.drain()
    
    def send_bitfield(self):
        generate_heading("Sending bitfield")
        length,bitfield = self.create_message()
        bitfield_message = struct.pack("!IB",length,5)
        bitfield_message += struct.pack(f"!{length-1}s", bitfield)
    
    def update_bitfield(self, piece_index):
        generate_heading(f"Updated {self.ip} | {self.port}")
        if (piece_index<self.no_pieces):
            self.present_bits[piece_index] = 1
    
    def set_bitfield(self, bitstring):
        generate_heading(f"Bitstring for {self.ip} | {self.port}: {bitstring}")
        for i in range(self.no_pieces):
            if (bitstring[i]):
                self.present_bits[i] = 1
            else:
                self.present_bits[i] = 0

    async def begin(self):
        try:
            # reader,writer=await asyncio.open_connection(self.ip,self.port)
            await self.send_handshake()
            await self.send_interested()
            self.am_interested=1

            self.began_at = round(time.time())

            while True:
                try:
                    recv_data=await asyncio.wait_for(self.reader.read(65535),2)
                    if len(recv_data)>4:
                        offset=0
                        msg_len=struct.unpack_from("!i",recv_data)[0]
                        offset+=4
                        msg_id=struct.unpack_from("!B",recv_data,offset)[0]
                        offset+=1
                        if msg_id==0:
                            generate_heading(f"Choked by {self.ip} | {self.port}")
                            self.peer_choking=1
                        if msg_id==1:
                            generate_heading(f"Unchoked by {self.ip} | {self.port}")
                            self.peer_choking=0
                        if msg_id==2:
                            generate_heading(f"Interested {self.ip} | {self.port}")
                        if msg_id==3:
                            generate_heading(f"Not Interested {self.ip} | {self.port}")
                        if msg_id==4:
                            generate_heading(f"Have {self.ip} | {self.port}")
                            piece_index=struct.unpack_from("!i",recv_data,offset)[0]
                            self.update_bitfield(piece_index)
                        if msg_id==5:
                            generate_heading(f"BitField {self.ip} | {self.port}")
                            bitfield=recv_data[offset:]
                            bitfield=bitstring.BitArray(bitfield).bin
                            self.set_bitfield(bitfield)
                            # print(self.ip,'---------',self.port,"-------",self.present_bits)
                        if msg_id==6:
                            generate_heading(f"Request {self.ip} | {self.port}")
                        if msg_id==7:
                            s=recv_data[5:]
                            while(len(s)<msg_len-1):
                                s+=await asyncio.wait_for(self.reader.read(msg_len-1),10)
                            # generate_heading(f"Piece Received from {self.ip} | {self.port}")
                            self.num_downloaded_blocks += 1
                            # generate_heading(f"Piece Received from {self.ip} | {self.port} | {self.download_start} | {time.time()} | {self.num_downloaded_blocks} | {msg_len-9}")
                            self.get_download_rate(msg_len-9)
                            self.update_rate(self.download_rate,self.ip,self.port)
                            offset=0
                            piece_index=struct.unpack_from("!i",s,offset)[0]
                            offset+=4
                            block_offset=struct.unpack_from("!i",s,offset)[0]
                            offset+=4
                            block=s[offset:]
                            # generate_heading(f"block length: {len(block)}")
                            self.downloading=0
                            await self.write_block(piece_index,block_offset,block)
                            # await asyncio.sleep(1)
                        if msg_id==8:
                            generate_heading(f"Cancel {self.ip} | {self.port}")
                    # generate_heading(f"166:- Interested: {self.am_interested} | Choking: {self.peer_choking} | Downloading: {self.downloading} | {self.ip} | {self.port}")
                        if (self.am_interested and self.peer_choking==0 and self.downloading==0 and np.sum(self.present_bits)>0):
                            piece_no, block_offset, block_size, piece_status=self.get_piece_block(self.ip,self.port)
                            if(piece_status==True):
                                self.writer.close()
                                # await self.writer.wait_closed()
                                break
                            if(piece_no==None):
                                # print("yay")
                                pass
                            else:
                                # generate_heading(f"Requesting {piece_no} | {block_offset} | {block_size} | using {self.ip} | {self.port}")
                                if(self.present_bits[piece_no]==1):
                                    self.downloading=1
                                    self.send_request_message(piece_no,block_offset,block_size)
                                    self.download_start = time.time()

                            
                            # piece_no,piece_status,exp = self.get_piece_index()
                            # print(piece_no,piece_status,exp)
                            # print(f"Here 1 {piece_no}")
                            # if piece_status==True:
                            #     self.writer.close()
                            #     # self.complete()
                            #     break
                            # if self.present_bits[piece_no]==1:
                            #     print(f"Here 2")
                            #     self.downloading=1
                            #     block_offset,block_length =self.find_next_block(piece_no,exp)
                            #     print(f"Here 3 {piece_no} | {block_offset}")
                            #     generate_heading(f"Requesting {piece_no} from {self.ip} | {self.port}")
                            #     self.send_request_message(piece_no,block_offset,block_length)
                            #     self.in_download_piece = piece_no
                            #     self.in_download_block = block_offset
                            #     self.in_download_length = block_length
                        current = round(time.time())
                        if (current>self.began_at + 120):
                            self.began_at = current
                            self.send_keep_alive()
                
                except ConnectionResetError:
                    print("Connection reset error")
                    self.writer.close()
                    # await self.writer.wait_closed()
                    break
                except Exception as e:
                    # exc_type, exc_obj, exc_tb = sys.exc_info()
                    # fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                    # print(exc_type, fname, exc_tb.tb_lineno)
                    # print(self.downloading,e)
                    if(self.allDownloaded()):
                        self.writer.close()
                        # await self.writer.wait_closed()
                        break
                    else:
                        pass


                    # exc_type, exc_obj, exc_tb = sys.exc_info()
                    # fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                    # print(exc_type, fname, exc_tb.tb_lineno)
                    # p,ps,_=self.get_piece_index()
                    # if(ps==True):
                    #     print("Closing other peers as all pieces done")
                    #     self.writer.close()
                    #     break
                    
                    # pass
        except Exception as e:
            self.writer.close()


    # def read_and_write_messages(self,client):
    #     client.settimeout(None)
    #     while True:
    #         try:
    #             recv_data=client.recv(65535)
    #             if len(recv_data)>4:
    #                 offset = 0
    #                 msg_len=struct.unpack_from("!i",recv_data)[0]
    #                 offset += 4
    #                 msg_id=struct.unpack_from("!B",recv_data, offset)[0]
    #                 offset+=1

    #                 if msg_id==0:
    #                     generate_heading("Choke")
    #                     self.peer_choking = 1
    #                 elif msg_id==1:
    #                     generate_heading(f"Unchoke by ({self.ip, self.port, self.id})")
    #                     self.peer_choking = 0
    #                 elif msg_id==2:
    #                     generate_heading("Interested")
    #                 elif msg_id==3:
    #                     generate_heading("Not Interested")
    #                 elif msg_id==4:
    #                     generate_heading("Have")
    #                     piece_index = struct.unpack_from("!i", recv_data, offset)[0]
    #                     print("Piece index: ", piece_index)
    #                     self.update_bitfield(piece_index)
    #                 elif msg_id==5:
    #                     generate_heading("BitField")
    #                     bitfield = recv_data[offset:]
    #                     bitfield = bitstring.BitArray(bitfield).bin
    #                     self.set_bitfield(bitfield)
    #                 elif msg_id==6:
    #                     generate_heading("Request")
    #                 elif msg_id==7:
    #                     generate_heading("Piece")
    #                     piece_index = struct.unpack_from("!i",recv_data,offset)[0]
    #                     offset+=4
    #                     block_offset = struct.unpack_from("!i",recv_data,offset)[0]
    #                     offset+=4
    #                     block = recv_data[offset:]
    #                     self.write_block(piece_index,block_offset,block,self.ip,self.port)
    #                     self.downloading = 0
    #                 elif msg_id==8:
    #                     generate_heading("Cancel")
                    
    #                 if (self.am_interested and self.peer_choking==0 and self.downloading==0):
    #                     piece_index = 0
    #                     if self.present_bits[piece_index]==1:
    #                         self.downloading = 1
    #                         block_offset,block_length,status = self.find_next_block(piece_index)
    #                         if (status==True):
    #                             generate_heading("Done")
    #                             break
    #                         self.send_request_message(client,piece_index,block_offset,block_length)
    #                     else:
    #                         self.send_keep_alive(client)
    #                         print(f"Piece with index ({piece_index}) was not found with the peer {self.ip, self.port, self.id}")

    #         except Exception as e:
    #             print(e)
    #             pass