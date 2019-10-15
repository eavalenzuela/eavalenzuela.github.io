---
layout: post
title: Defensive OSINT Automation
---

## Or, "Stop paying people to Google for you, and write some Python!"

#### Impetus

OSINT is often something defenders forget to do or care about until it's too late, and even then OSINT's role in an incident may go completely unnoticed or unappreciated. Very few security engineers I've talked with have any kind of OSINT monitoring program at their company, much less automation or custom tools.

Before settling on building this tooling myself, I shopped around for some of the popular commercial OSINT monitoring offerings, like hackertarget.com and Signal(getsignal.info). There're a ton of them, and most of them are either buzzword-fests(you don't need to monitor The Dark Web™... no one is talking about you), or extremely simplistic ("run nmap or Nessus on your servers from our handy UI!").

Eventually I looked up and realized I could do this better myself, 100% customized to the environment and threats.

#### Solution

At a high level, it's just a number of python services running in discrete containers in ECS, talking to a database server. This works really well, because 1) I never used ECR+ECS and I wanted to learn, and 2) I can add new modules without messing up the other monitor modules, and without having to run a whole server instance for a couple measly Python scripts(I used Fargate).

The initial modules I built were:

* GitHub public repository monitor
* Certificate Transparency List monitor
* External service monitor (w/nmap)
* News/forum/blog monitor (w/Google Custom Search Engine [CSE])

##### Update, Oct 2019: There are now 2 additional modules:

* Paste-site (specifically, Pastebin for now) monitoring
* Subdomain monitoring

Subdomain monitoring is accomplished with SecurityTrail's subdomain API endpoint, and is just intended to give us a head's-up if new subdomain DNS records are created.

Pastebin monitoring uses Pastebin's scraping API. It checks the content of each paste against a list of keywords and regex patterns, and performs actions based on per-expression settings. For example, certain keywords (e.g. the company name) will always be downloaded, so they can be reviewed without worrying about the paste being removed. In addition to company-related queries, several general queries are useful, to keep your finger on the pulse.

### GitHub Monitor

This uses the GitHub API to enumerate a list of organization-joined user accounts(non-personal accounts), and then polls their public account API info to ensure there are not any unauthorized public repositories. I super recommend this if you use GitHub, since you cannot prevent user accounts from creating repos. Some people seem to think this can't happen by accident(and of course, this won't stop a user intentionally trying to post code publicly), but yes, sometimes even experienced devs will make a repo public without meaning to.

### Certificate Transparency List Monitor

If you're not monitoring certificate issuance for your domain, you should be. It's a great way to spot potential attacks before they even start, since a lot of phishing actors will set up typo-squatting or subdomain certificates well before they start to actually send phishing messages to users. I made use of crt.sh's RSS feed function + python's feedreader, combined with some simple regex to help spot some simple typo-squatting techniques in addition to malicious subdomains.

### External Service Monitor

Hopefully you already have something doing this to some extent already as part of a vuln mgmt program, but in my case this was less about knowing what external services were running at any particular time, and more about knowing when new services popped up, and when existing services were closed.

Nmap + a horrifying mass of nested-case xml parsing was the flavor of the day. I read several blogs on nmap parsing, and suffice it to say that I blame nmap themselves for not adding json or some other controlled-structure format for this. It's awful, but it *is* working.

### News + Forum + Blog Monitor

This module was an interesting one, since it came about from seeing people discuss us on several forums after-the-fact. For large companies, this won't matter, and you can't feasibly monitor that stuff anyways, but for small/medium companies, knowing what people are saying in an 'unprompted' environment is very important, both from a marketing and security side.

Thankfully, Google has a set of pseudo-deprecated tools for creating and querying a Custom Search Engine (CSE), which allows you to prioritize searches on specific sites in addition to the web at large, and having an API to do it with.

Paired with a list of 'search phrase + risk rating' pairs fed to it, you have cheap and simple (and basic) monitoring for public discussion.

### Backend Database

To store the gathered info, I set up a simple mysql database on a t2.small instance. I initially set this up with RDS, but realized it was overkill for the miniscule volume of data I'm storing.

GitHub Monitr columns:

* repo_name
* owner_account
* approved_for_public
* last_seen (by script)
* fork (boolean)
* company_repo (boolean)

Certificate Monitor columns:

* domain
* san (list of SANs)
* issuer
* fingerprint
* start_time (cert valid from date)
* first_seen (by the monitor script)
* source (e.g. 'crt.sh')

External Service Monitor columns:

* ip_address
* hostname
* port
* service
* first_seen
* last_seen
* md5 (hashed ip+port+service to use as unique identifier)

News Monitor columns:

* query_term
* title (Google Search result title)
* url
* risk (set in query term file), e.g. "salesforce breach:High"
* needs_review (boolean, 1 for med/high, 0 for low)
* last_seen
* md5 (query_term + url)


