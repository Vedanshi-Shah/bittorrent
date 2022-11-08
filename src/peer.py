from socket import *
import struct
import bitstring
import sys
import random
from prettify import generate_heading, keys_values
import asyncio
import numpy as np
import time

class Peer:
    def __init__(self,peer_id,info_hash,ip,port,no_pieces,find_next_block,write_block,get_piece_index):
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
        self.reader=None
        self.writer=None
        self.in_download_block = None
        self.in_download_piece = None
        self.in_download_length = None
    
    def send_interested(self):
        # try:
        interested_msg=struct.pack("!Ib",1,2)
        # self.writer.write(interested_msg)
        # self.writer.drain()
        self.sock.send(interested_msg)
        # except Exception as e:
        #     print("Here")
        #     print(e)
        #     return {"status":0}

    def send_handshake(self):
        generate_heading(f"Sending Handshake to {self.ip} | {self.port}")
        handshake_msg=struct.pack("!b19sq20s20s",19,"BitTorrent protocol".encode(),0,self.info_hash,self.id.encode())
        self.sock.send(handshake_msg)
        # self.writer.write(handshake_msg)
        # self.writer.drain()
        s=b''
        # Can receive a BitField after handshake
        # s+=asyncio.wait_for(self.reader.read(65535),10) # wait for 10 seconds to receive data
        s+=self.sock.recv(68)
        # s+=self.sock.recv(68)
        if (len(s)<68):
            generate_heading("Corrupted message")
            return
        decoded_recv_data = struct.unpack("!b19sq20s20s", s[:68])
        if decoded_recv_data[3] != self.info_hash:
            raise Exception("Invalid Peer Connection")

    def connect(self):
        try:
            print(self.ip, self.port)
            # self.reader,self.writer = asyncio.wait_for(asyncio.open_connection(self.ip,self.port),4)
            self.sock = socket(AF_INET, SOCK_STREAM)
            self.sock.settimeout(3)
            self.sock.connect((self.ip, self.port))
            
        except (Exception,) as e:
            self.reader=None
            self.writer=None
            print(e)

    def send_request_message(self,piece_index,block_offset,block_length):
        # Index, Block Offset, Block length
        print(piece_index, block_offset, block_length)
        req_message=struct.pack("!IB",13,6)
        payload = struct.pack("!i", piece_index)
        payload += struct.pack("!i", block_offset)
        payload += struct.pack("!i", block_length)
        req_message += payload
        # print(f"Requesting (piece_index = {piece_index}, block_offset = {block_offset}, block_length = {block_length}) from {self.ip} | {self.port}...")
        # self.writer.write(req_message)
        # self.writer.drain()
        self.sock.send(req_message)
        generate_heading("Request sent")
    
    def send_keep_alive(self):
        generate_heading("Sending Keep Alive")
        keep_alive_message = struct.pack("!I",0)
        # self.writer.write(keep_alive_message)
        # self.writer.drain()
        self.sock.send(keep_alive_message)
    
    def update_bitfield(self, piece_index):
        generate_heading(f"Updated {self.ip} | {self.port}: {bitstring}")
        if (piece_index<self.no_pieces):
            self.present_bits[piece_index] = 1
    
    def set_bitfield(self, bitstring):
        generate_heading(f"Bitstring for {self.ip} | {self.port}: {bitstring}")
        for i in range(len(bitstring)):
            if (bitstring[i]):
                self.present_bits[i] = 1
            else:
                self.present_bits[i] = 0

    def begin(self):
        try:
            # reader,writer=asyncio.open_connection(self.ip,self.port)
            self.send_handshake()
            self.send_interested()
            self.am_interested=1

            self.began_at = round(time.time())

            while True:
                try:
                    # recv_data=asyncio.wait_for(self.reader.read(65535),2)
                    recv_data = self.sock.recv(65535)
                    if len(recv_data)>4:
                        offset=0
                        msg_len=struct.unpack_from("!i",recv_data)[0]
                        offset+=4
                        msg_id=struct.unpack_from("!B",recv_data,offset)[0]
                        offset+=1
                        if msg_id==0:
                            generate_heading(f"Choked by {self.ip} | {self.port}")
                            self.peer_choking=1
                        elif msg_id==1:
                            generate_heading(f"Unchoked by {self.ip} | {self.port}")
                            self.peer_choking=0
                        elif msg_id==2:
                            generate_heading("Interested")
                        elif msg_id==3:
                            generate_heading("Not Interested")
                        elif msg_id==4:
                            generate_heading("Have")
                            piece_index=struct.unpack_from("!i",recv_data,offset)[0]
                            self.update_bitfield(piece_index)
                        elif msg_id==5:
                            generate_heading("BitField")
                            bitfield=recv_data[offset:]
                            bitfield=bitstring.BitArray(bitfield).bin
                            self.set_bitfield(bitfield)
                            print(self.ip,'---------',self.port,"-------",self.present_bits)
                        elif msg_id==6:
                            generate_heading("Request")
                        elif msg_id==7:
                            generate_heading(f"Piece Received from {self.ip} | {self.port}")
                            piece_index=struct.unpack_from("!i",recv_data,offset)[0]
                            offset+=4
                            block_offset=struct.unpack_from("!i",recv_data,offset)[0]
                            offset+=4
                            block=recv_data[offset:]
                            self.write_block(piece_index,block_offset,block,self.ip,self.port)
                            self.downloading=0
                        elif msg_id==8:
                            generate_heading("Cancel")
                        # generate_heading(f"Interested: {self.am_interested} | Choking: {self.peer_choking}")
                        if (self.am_interested and self.peer_choking==0 and self.downloading==0):
                            piece_no,piece_status = self.get_piece_index()
                            if piece_status==True:
                                # self.writer.close()
                                generate_heading("Done")
                                self.sock.close()
                                break
                            print(self.present_bits)
                            if self.present_bits[piece_no]==1:
                                self.downloading=1
                                block_offset,block_length = self.find_next_block(piece_no)
                                generate_heading(f"Requesting {piece_no}")
                                self.send_request_message(piece_no,block_offset,block_length)
                                self.in_download_piece = piece_no
                                self.in_download_block = block_offset
                                self.in_download_length = block_length
                except (Exception,) as e:
                    if (self.in_download_piece!=None):
                        generate_heading(f"Requesting {self.in_download_piece} again")
                        self.send_request_message(self.in_download_piece,self.in_download_block,self.in_download_length)
                    print(f"Error: {e}")
                    pass
                else:
                    current = round(time.time())
                    if (current>self.began_at + 120):
                        self.began_at = current
                        self.send_keep_alive()
        except (Exception,) as e:
            print(e)


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