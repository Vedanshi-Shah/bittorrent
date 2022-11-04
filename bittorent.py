"""
    All of the remaining messages in the protocol take the form of <length prefix><message ID><payload>
    The length prefix is a four byte big-endian value. The message ID is a single decimal byte. The payload is message dependent
    
    9 different messages

    keep-alive
        len=0
        no mid and payload
        maintain connection alive
    
    choke
        len=1
        id=0
        no payload
    
    unchoke
        len=1
        id=1
        no payload
    
    interested
        len=1
        id=2
        no payload
    
    not interested
        len=1
        id=3
        no payload
    
    have
        len=5
        id=4
        piece index: 0-based
    
    bitfield
        len=1+X
        id=5
        bitfield
    
    request
        len=13
        id=6
        index,begin,length
    
    piece
        len=9+x
        id=7
        index,begin,block

    cancel
    - used during end game
        len=13
        id=8
        index,begin,length
    
    port
    - for DHT

    port
    
    Clients should drop the connection if they receive bitfields that are not of the correct size, or if the bitfield has any of the spare bits set

    * Some clients (Deluge for example) send bitfield with missing pieces even if it has all data
"""