from socket import *
import struct
import sys
class Peer:
    def __init__(self,peer_id,info_hash,ip,port,no_pieces):
        self.ip=ip
        self.port=port
        self.am_choking=1
        self.am_interested=0
        self.peer_chocking=1
        self.peer_interested=0
        self.info_hash=info_hash
        self.id=peer_id
        self.remote_id=''
        self.present_bits=[0]*no_pieces

    def send_handshake(self,client):
        handshake_msg=struct.pack("!b19sq20s20s",19,"BitTorrent protocol".encode(),0,self.info_hash,self.id.encode())
        client.send(handshake_msg)
        s=b''
        client.settimeout(2)
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
                client.settimeout(2)
        return {"status":1}
    
    def send_interested(self,client):
        try:
            interested_msg=struct.pack("!Ib",1,2)
            client.send(interested_msg)
        except Exception as e:
            print(e)
            return {"status":0}
        self.am_interested=1
        return {"status":1}

    def read_and_write_messages(self,client):
        while True:
            try:
                recv_data=client.recv(65535)
                while len(recv_data)>4:
                    msg_len=struct.unpack("!i",recv_data[:4])[0]
                    msg_id=int(recv_data[4])
                    print(msg_len,msg_id)
            except Exception as e:
                print(e)
                sys.exit(0)