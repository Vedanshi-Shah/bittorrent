* Peers may close a connection if they receive no messages (keep-alive or any other message) for a certain period of time, so a keep-alive message must be sent to maintain the connection alive if no command have been sent for a given amount of time. This amount of time is generally two minutes.
* Optimistic Choke/Unchoke
    * Every 10 seconds, the interested remote peers are ordered according to their download rate to the local peer and the 3 fastest peers are unchoked
    * Every 30 seconds, one additional interested remote peer is unchoked at random. We call this random unchoke the optimistic unchoke
