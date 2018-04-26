---
layout: post
title: Scapy_RPC_Layer
---

# RPC Layer for Scapy

A custom-built(but very bare-bones) extension for [scapy](https://github.com/secdev/scapy), this layer allows you to send simple RPC packets in a structured way.

## Overview

This was made necessary because the existing RPC tools(chiefly rpcinfo) do not have support for modifying low-level settings like the source port, and because of an alert indicating that an RPC portmap request had been made against our servers, and I wanted to verify this wasn't returning any data(it wasn't... but it was a great learning opportunity!).

## [The Tool](https://github.com/eavalenzuela/scapy_RPC_layer)

## Build Methodology

To construct this layer, packet captures of rpcinfo portmap requests were viewed, and the field lengths determined(**note:** interestingly, all fields in the portmap request were 4 bytes)

Looking at the relevant RFC (RFC5531), the proper field names, order, and default values were determined.

These fields were then used for a very basic scapy layer skeleton:

```
class RPCCall(Packet):
    name = "Remote Procedure Call"
    fields_desc = [
            IntField("xid", 1),
            IntField("msg_type", 0),
            IntField("rpcvers", 2),
            IntField("prog", 100000),
            IntField("vers", 2),
            IntField("proc", 4),
            IntField("cred_flavor", 0),
            IntField("cred_len", 0),
            IntField("verifier_flavor", 0),
            IntField("verifier_len", 0)]
```

The layer was then added to the **config.py** file's 'load_layers' array.

```
load_layers = ["l2", "inet", "dhcp", "dns", "dot11", "gprs",
                   "hsrp", "inet6", "ir", "isakmp", "l2tp", "mgcp",
                   "mobileip", "netbios", "netflow", "ntp", "ppp", "pptp",
                   "radius", "rip", "rtp", "skinny", "smb", "snmp",
                   "tftp", "x509", "bluetooth", "dhcp6", "llmnr",
                   "sctp", "vrrp", "ipsec", "lltd", "vxlan", "eap", "rpc"]
```

At this point, it is ready for use in scapy(although very ugly and finnicky).

## Testing the Layer

Firing up python, the augmented scapy can be imported from the folder above /scapy using ```from scapy.all import *```.

You can then begin constructing basic RPCCall packets like so:

![pkt_build]({{site.url}}/assets/images/pkt_build.png)

Note that the Ether layer is loaded, but it left for automatic initialization by scapy, and no fields are specified.

The request can then be sent, and a reponse listened for. Because the Ether layer was used, sendp/srp/srp1 must be used for sending rather than send/sr/sr1.

![pkt_sr]({{site.url}}/assets/images/pkt_sr.png)

We can see that a response was recieved, even if it's not easy to tell what the response means.

Looking in Wireshark, we can see that the sent packet was indeed recognized as a RPC portmap call, and that the response recieved is an RPC portmap reply.

![ws_pkts]({{site.url}}/assets/images/ws_pkts.png)

We can then further dive into the reply, and see what services the portmap service notified us of.

![ws_reply]({{site.url}}/assets/images/ws_reply.png)

## Final Thoughs

This is by no means a complete or even truly usable layer, other than for the specific use-case it was built for(testing portmapper calls from specific source ports).

To use this effectively, you'd want separate Portmap_Request and Portmap_Reply layers, and that would only cover the portmap service, which is one of many RPC services out there(which is probably why the scapy team has not made RPC layers).

