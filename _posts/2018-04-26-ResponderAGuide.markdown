---
layout: post
title: Intro to Responder
---

# Responder

A Python tool for poisoning certain network name-resolution protocols(and then stealing the credentials sent afterwards), [Responder](https://github.com/lgandx/Responder) is commonly used by red teams during pentests to elevate privileges by relying on peoples' computers being configured to automatically, periodically, connect to network shares or other systems which do not have proper DNS entries(this actually is much more common than you would think).

## How it works

### The Protocols

![rsp_protocols]({{ '/assets/images/rsp_protocols.png' | relative_url }})

#### 1. LLMNR

Per defining [RFC 4795](https://datatracker.ietf.org/doc/html/rfc4795):
>The goal of Link-Local Multicast Name Resolution (LLMNR) is to enable name resolution in scenarios in which conventional DNS name resolution is not possible. 

>LLMNR supports all current and future DNS formats, types, and classes, while operating on a separate port from DNS, and with a distinct resolver cache.  Since LLMNR only operates on the local link, it cannot be considered a substitute for DNS.

#### 2. MDNS

Per defining [RFC 6762](https://datatracker.ietf.org/doc/html/rfc6762):
>Multicast DNS (mDNS) provides the ability to perform DNS-like operations on the local link in the absence of any conventional Unicast DNS server.

>The primary benefits of Multicast DNS names are that 
>* (i) they require little or no administration or configuration to set them up,
>* (ii) they work when no infrastructure is present, and
>* (iii) they work during infrastructure failures.

#### 3. NBT-NS

Per defining [RFCs 1001/1002](https://datatracker.ietf.org/doc/html/rfc1002):
>This RFC defines a proposed standard protocol to support NetBIOS services in a TCP/IP environment.  Both local network and internet operation are supported.  Various node types are defined to accommodate local and internet topologies and to allow operation with or without the use of IP broadcast.

NBT (NetBIOS) itself does not have an RFC, as it is not actually a network protocol, but rather an [API](https://web.archive.org/web/2018/https://technet.microsoft.com/en-us/library/cc958773.aspx) developed by Microsoft:

```NetBIOS is a standard application programming interface in the personal-computing environment. NetBIOS is used for developing client/server applications. NetBIOS has been used as an interprocess communication (IPC) mechanism since its introduction.```

### Putting it together

All 3 of these protocols allow you to perform name lookups and communication on the local link(subnet) without needing or allowing for a trusted intermediary like a DNS server.

This effectively means that for these protocols, when a request for a lookup is sent, **the first client to respond is considered the trusted client**.

## How Responder Works

Responder performs 2 primary functions:
1. responding to any LLMNR, NBT-NS, and MDNS requests *quickly* ("poisoning" them)
2. operating the services those now-MitM'd clients are expecting (e.g. HTTP/S, FTP, **SMB**, LDAP, SQL, Kerberos, etc)

Once a request has been poisoned, the Responder daemon will wait for whatever service the originator is trying to access, as the next step for the client is sending credentials to the server to authenticate to the service.

![rsp_chain]({{ '/assets/images/rsp_chain.png' | relative_url }})

----

## Running Responder

```
$> python responder.py
```

Options | Alternate | Function
------- | --------- | --------
-h | --help | displays help info
-A | --analyze | does not poison any requests. This allows you to monitor traffic and pick out specific targets without potentially blocking a lot of machines from communicating properly
-I | --interface= | local network interface to use
-i | --ip= | local IP to use (OSX only)
-f | --fingerprint | use LLMNR or NBT-NS requests to fingerprint the OS of the client
-w | --wpad | run the wpad proxy server
-F | --ForceWpadAuth | force clients to authenticate in order to retrieve the wpad proxy file. This can be a good way to capture credentials, but it is very intrusive, and very obvious to defenders
-v | --verbose | increases verbosity



Launching responder in Analyze mode:

![rsp_init]({{ '/assets/images/rsp_init.png' | relative_url }})

____

Clients beginning to populate over the network:

![rsp_clients]({{ '/assets/images/rsp_clients.png' | relative_url }})

____

A set of LLMNR and NBT-NS requests that are potentially vulnerable to poisoning and credential theft:

![rsp_vulnerables]({{ '/assets/images/rsp_vulnerables.png' | relative_url }})
