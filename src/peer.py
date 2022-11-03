class Peer:
    def __init__(self,peer_id,info_hash,ip,port):
        self.ip=ip
        self.port=port
        self.am_choking=1
        self.am_interested=0
        self.peer_chocking=1
        self.peer_interested=0
        self.info_hash=info_hash
        self.id=peer_id
        self.remote_id=''

