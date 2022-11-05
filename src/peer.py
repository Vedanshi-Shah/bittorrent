from socket import *
import struct
import bitstring
import sys
import random
from prettify import generate_heading, keys_values
class Peer:
    def __init__(self,peer_id,info_hash,ip,port,no_pieces,find_next_block,write_block):
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
        self.present_bits=[0]*no_pieces
        self.no_pieces = no_pieces
        self.find_next_block = find_next_block
        self.write_block = write_block

    def send_handshake(self,client):
        handshake_msg=struct.pack("!b19sq20s20s",19,"BitTorrent protocol".encode(),0,self.info_hash,self.id.encode())
        client.send(handshake_msg)
        s=b''
        client.settimeout(2)
        # Can receive a BitField after handshake
        while True:
            try:
                recv_data = client.recv(68)
                s += recv_data
                decoded_recv_data = struct.unpack("!b19sq20s20s", s)
                if decoded_recv_data[3] != self.info_hash:
                    print("Invalid peer closing connection")
                    return {"status":0}
                break
            except (Exception,):
                # print("Here")
                # client.settimeout(2)
                return {"status": 0}
        return {"status":1}
    
    def send_interested(self,client):
        # try:
        interested_msg=struct.pack("!Ib",1,2)
        client.send(interested_msg)
        # except Exception as e:
        #     print("Here")
        #     print(e)
        #     return {"status":0}
        self.am_interested=1
        return {"status":1}
    
    def send_request_message(self,client,piece_index,block_offset,block_length):
        req_message=struct.pack("!IB",13,6)
        # Index, Block Offset, Block length
        print(piece_index, block_offset, block_length)
        payload = struct.pack("!i", piece_index)
        payload += struct.pack("!i", block_offset)
        payload += struct.pack("!i", block_length)
        req_message += payload
        print(f"Requesting (piece_index = {piece_index}, block_offset = {block_offset}, block_length = {block_length})...")
        client.send(req_message)
    
    def send_keep_alive(self, client):
        keep_alive_message = struct.pack("!I",0)
        client.send(keep_alive_message)
    
    def update_bitfield(self, piece_index):
        if (piece_index<self.no_pieces):
            self.present_bits[piece_index] = 1
    
    def set_bitfield(self, bitstring):
        print(bitstring)
        for i in range(len(bitstring)):
            if (bitstring[i]):
                self.update_bitfield(i)
            else:
                self.present_bits[i] = 0

    def read_and_write_messages(self,client):
        client.settimeout(None)
        while True:
            # try:
                recv_data=client.recv(65535)
                if len(recv_data)>4:
                    offset = 0
                    msg_len=struct.unpack_from("!I",recv_data)[0]
                    generate_heading(f"Message Length: {msg_len}")
                    offset += 4
                    msg_id=struct.unpack_from("!B",recv_data, offset)[0]
                    offset+=1

                    if msg_id==0:
                        generate_heading("Choke")
                        self.peer_choking = 1
                    elif msg_id==1:
                        generate_heading(f"Unchoke by ({self.ip, self.port, self.id})")
                        self.peer_choking = 0
                    elif msg_id==2:
                        generate_heading("Interested")
                    elif msg_id==3:
                        generate_heading("Not Interested")
                    elif msg_id==4:
                        generate_heading("Have")
                        piece_index = struct.unpack_from("!i", recv_data, offset)[0]
                        print("Piece index: ", piece_index)
                        self.update_bitfield(piece_index)
                    elif msg_id==5:
                        generate_heading("BitField")
                        bitfield = recv_data[offset:]
                        bitfield = bitstring.BitArray(bitfield).bin
                        self.set_bitfield(bitfield)
                    elif msg_id==6:
                        generate_heading("Request")
                    elif msg_id==7:
                        generate_heading("Piece")
                        piece_index = struct.unpack_from("!i",recv_data,offset)[0]
                        offset+=4
                        block_offset = struct.unpack_from("!i",recv_data,offset)[0]
                        offset+=4
                        block = recv_data[offset:]
                        # print(type(block))
                        # print(offset)
                        # print(block)
                        # print(len(block.decode()))
                        print(f"Received block: (piece_index = {piece_index}, block_offset = {block_offset}, block_length={len(block)}")
                        print()
                        self.write_block(piece_index,block_offset,block,self.ip,self.port)
                        self.downloading = 0
                        client.close()
                        break
                    elif msg_id==8:
                        generate_heading("Cancel")
                    
                    keys_values({"interested": self.am_interested, "choking": self.peer_choking})
                    if (self.am_interested and self.peer_choking==0 and self.downloading==0):
                        # Can send the request
                        # So, for this, pick out a random piece
                        # Request for that piece only if it is with this peer
                        # piece_index = random.randint(0, self.no_pieces)
                        print("Here")
                        # piece_index = random.randint(0, self.no_pieces-1)
                        piece_index = 0
                        # Is this piece with the peer?
                        if self.present_bits[piece_index]==1:
                            # Send the request
                            self.downloading = 1
                            print(f"Trying to request piece {piece_index} from ({self.ip, self.port, self.id})")
                            block_offset,block_length,status = self.find_next_block(piece_index)
                            print(f"Need to request for {block_offset} | {block_length}, {status}")
                            self.send_request_message(client,piece_index,block_offset,block_length)
                        else:
                            # Send keep alive
                            self.send_keep_alive(client)
                            print(f"Piece with index ({piece_index}) was not found with the peer {self.ip, self.port, self.id}")

            # except Exception as e:
            #     print(e)
            #     client.settimeout(2)
            #     # sys.exit(0)