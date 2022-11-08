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
