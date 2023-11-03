#/bin/bash

# /usr/bin/libcamera-vid -t 0 --inline -o - | cvlc stream:///dev/stdin --sout '#rtp{sdp=rtsp://:8554/stream}' :demux=h264


/usr/bin/libcamera-vid -t 0 --inline --listen -o tcp://0.0.0.0:6000