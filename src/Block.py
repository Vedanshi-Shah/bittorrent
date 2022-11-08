import heapq
import time

class Block:
    def __init__(self,piece,offset,size):
        self.piece=piece
        self.offset=offset
        self.size=size
        self.status=0
        self.began_requesting=time.time()
        self.data=b''
        #staus 0 not yet requested, 1 -> requested, 2-> requested and received
    
    def __lt__(self,other):
        return self.began_requesting<other.began_requesting
    
