# Tech by Math, Networks tutorial 8: masks, subnets and longest-prefix match, done with integers and
# checked against Python's standard ipaddress module.
import ipaddress as ip


def to_int(a):
    return int(ip.IPv4Address(a))


def bits(n):
    return ".".join(f"{(n >> s) & 255:08b}" for s in (24, 16, 8, 0))


print("Part 1. 192.168.10.77/26 by hand")
addr, plen = to_int("192.168.10.77"), 26
mask = (0xFFFFFFFF << (32 - plen)) & 0xFFFFFFFF
net, bcast = addr & mask, (addr & mask) | (~mask & 0xFFFFFFFF)
print(f"   address   {bits(addr)}  {ip.IPv4Address(addr)}")
print(f"   mask /26  {bits(mask)}  {ip.IPv4Address(mask)}")
print(f"   AND       {bits(net)}  {ip.IPv4Address(net)}   (network)")
print(f"   broadcast {bits(bcast)}  {ip.IPv4Address(bcast)}")
print(f"   2^(32-26) = {2 ** (32 - plen)} addresses, {2 ** (32 - plen) - 2} usable hosts")
n = ip.ip_network("192.168.10.77/26", strict=False)
print(f"   ipaddress module: network {n.network_address}, broadcast {n.broadcast_address}, {n.num_addresses} addresses")

print("\nPart 2. Cutting 10.20.0.0/22 into pieces")
big = ip.ip_network("10.20.0.0/22")
print(f"   {big}: {big.num_addresses} addresses")
for new in (24, 26):
    subs = list(big.subnets(new_prefix=new))
    print(f"   /{new}: {len(subs)} subnets = 2^({new}-22); first {subs[0]}, second {subs[1]}, last {subs[-1]}")

print("\nPart 3. Longest-prefix match")
table = [("0.0.0.0/0", "internet"), ("10.0.0.0/8", "core"), ("10.20.0.0/16", "campus"),
         ("10.20.4.0/22", "lab"), ("10.20.6.128/25", "printers")]


def lpm(dst):
    d, best = to_int(dst), None
    for prefix, hop in table:
        a, l = prefix.split("/")
        l = int(l)
        m = (0xFFFFFFFF << (32 - l)) & 0xFFFFFFFF if l else 0
        if d & m == to_int(a) and (best is None or l > best[0]):
            best = (l, prefix, hop)
    return best


for dst in ("10.20.6.200", "10.20.6.5", "10.20.9.9", "10.99.1.1", "8.8.8.8"):
    l, prefix, hop = lpm(dst)
    check = max((p for p, _ in table if ip.ip_address(dst) in ip.ip_network(p)), key=lambda p: int(p.split("/")[1]))
    print(f"   {dst:<12} -> {prefix:<15} ({hop}){'' if check == prefix else '  DIFFERENT from ipaddress'}")
