---
layout: post
title: SecurityToolProjects
---

# Security Tool Projects

Over the past 4 months, I've worked on a number of security tools for work, mainly focused around packet-level functions.

#### asker.py

I built this to be a counterpart to responder.py, but for now it uses only LLMNR, and not NBT-NS or MDNS. It's purpose is to occasionally serve out fake LLMNR requests, using a user-supplied list of known-fake names(so the list should be populated with 'mis-typings' of actual resource names in your environment).
I have tested this against responder, and it does in fact cause responder to attempt a hijack, which can then be logged and alerted-on.

#### scapy RPC layer

A quick-and-dirty, custom layer for scapy that allows you to send and receive RPC calls in a structured way. It is *very* basic, but was a good way to learn about scapy layers, and how to build them.

#### (new) Multi-Service Honeypot

Another honeypot idea(a good solution to extend your visibility in your environment, especially when you have a lot of unmonitored services), this one is attempting to emulate 5 different listener services:
1. ssh
2. smb
3. ldap
4. http
5. https

Future updates will include more expansive reporting and logging integrations(logstash and *hopefully* Splunk).
