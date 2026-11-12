# Tech by Math, Networks tutorial 8: the Internet checksum (RFC 1071) of an IPv4 header, by 16-bit words.
hdr = bytes.fromhex("45000054a6f2400040010000c0a80a4dc0a80a01")   # checksum field (bytes 10-11) set to 0
words = [int.from_bytes(hdr[i:i + 2], "big") for i in range(0, 20, 2)]
print("16-bit words:", " ".join(f"{w:04x}" for w in words))
s = sum(words)
print(f"plain sum  = {s:#x}")
folded = (s & 0xFFFF) + (s >> 16)
print(f"fold carry = {s & 0xFFFF:#06x} + {s >> 16:#x} = {folded:#06x}")
ck = ~folded & 0xFFFF
print(f"checksum   = ones' complement of {folded:#06x} = {ck:#06x}")
filled = hdr[:10] + ck.to_bytes(2, "big") + hdr[12:]
s2 = sum(int.from_bytes(filled[i:i + 2], "big") for i in range(0, 20, 2))
print(f"receiver: sum with the checksum in place = {s2:#x}, folded = {(s2 & 0xFFFF) + (s2 >> 16):#06x} (0xffff means OK)")
bad = bytearray(filled)
bad[16] ^= 0x01                          # one bit flipped in the destination address
s3 = sum(int.from_bytes(bad[i:i + 2], "big") for i in range(0, 20, 2))
print(f"one bit flipped: folded sum = {(s3 & 0xFFFF) + (s3 >> 16):#06x} (not 0xffff: detected)")
sw = bytearray(filled)
sw[12:14], sw[14:16] = filled[14:16], filled[12:14]   # swap two 16-bit words of the source address
s4 = sum(int.from_bytes(sw[i:i + 2], "big") for i in range(0, 20, 2))
print(f"two words swapped: folded sum = {(s4 & 0xFFFF) + (s4 >> 16):#06x} (0xffff: NOT detected)")
