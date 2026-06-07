#!/bin/bash
# Kill-switch: blockerar all utgående trafik som inte går via VPN-tunneln.
set -e

iptables -F INPUT
iptables -F OUTPUT
iptables -F FORWARD

iptables -P INPUT DROP
iptables -P OUTPUT DROP
iptables -P FORWARD DROP

# Loopback (intern kommunikation)
iptables -A INPUT -i lo -j ACCEPT
iptables -A OUTPUT -o lo -j ACCEPT

# Docker DNS-resolver (127.0.0.11) går inte alltid via lo-interfacet
iptables -A OUTPUT -d 127.0.0.11 -p udp --dport 53 -j ACCEPT
iptables -A OUTPUT -d 127.0.0.11 -p tcp --dport 53 -j ACCEPT

# Tillåt svar på etablerade anslutningar (proxy-svar tillbaka till klient)
iptables -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
iptables -A OUTPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT

# Tillåt OpenVPN att ansluta ut till PIA:s servrar (UDP och TCP)
# PIA strong-configs använder UDP 1197, TCP 502
iptables -A OUTPUT -p udp -m multiport --dports 1194,1197,1198 -j ACCEPT
iptables -A OUTPUT -p tcp -m multiport --dports 501,502,1194,1197,1198 -j ACCEPT

# Tillåt all trafik via VPN-tunneln (tun-interfacet)
iptables -A INPUT -i tun+ -j ACCEPT
iptables -A OUTPUT -o tun+ -j ACCEPT

# Tillåt inkommande anslutningar till proxy och kontroll-API
iptables -A INPUT -p tcp --dport 8888 -j ACCEPT
iptables -A INPUT -p tcp --dport 8000 -j ACCEPT

echo "iptables kill-switch aktiv."
